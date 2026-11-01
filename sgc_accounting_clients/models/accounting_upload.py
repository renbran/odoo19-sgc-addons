# -*- coding: utf-8 -*-
import base64
import datetime
import hashlib
import logging
import re
import xmlrpc.client

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .accounting_bucket import DOC_TYPES, MAX_UPLOAD_ROWS, find_column, read_rows
from .accounting_client import LINK_TODO, rpc, rpc_error

_logger = logging.getLogger(__name__)

# Buckets booked as drafts into the client database. Bank statements, payroll
# and expense receipts follow in release 2; master data and other documents
# are reviewed by hand and never become entries.
BOOKED_TYPES = ("customer_invoices", "vendor_bills", "credit_notes", "payments")
# Network problems are retried on the next cron runs (10 min apart).
BOOKING_RETRIES = 4
# Plain constant: the to-do is found again by it to dedupe and close.
BOOKING_TODO = "Draft booking failed"
# bucket -> (document number, document date, counterparty) columns
MOVE_COLUMNS = {
    "customer_invoices": ("Invoice Number", "Invoice Date", "Customer Name"),
    "vendor_bills": ("Bill Number", "Bill Date", "Vendor Name"),
    "credit_notes": ("Credit Note Number", "Credit Note Date", "Party Name"),
}
MOVE_LABELS = {
    "out_invoice": "customer invoice",
    "in_invoice": "vendor bill",
    "out_refund": "customer credit note",
    "in_refund": "vendor credit note",
}
BOOKING_STATES = [
    ("pending", "Pending"),
    ("waiting", "Waiting for database"),
    ("done", "Processed"),
    ("failed", "Failed"),
    ("skipped", "Not booked"),
]


def _cell(headers, row, label):
    column = find_column(headers, label)
    return (row.get(column) or "").strip() if column else ""


def _number(raw, default=0.0):
    if not raw:
        return default
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        raise ValueError(_("%(value)r is not a number", value=raw)) from None


DATE_LABELS = ("Invoice Date", "Bill Date", "Credit Note Date", "Due Date", "Payment Date")
DMY_DATE = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$")


def _date(raw):
    try:
        return datetime.date.fromisoformat(raw[:10]).isoformat()
    except ValueError:
        raise ValueError(_("date %(value)r is not YYYY-MM-DD", value=raw)) from None


def _own(records, company_id):
    """Prefer the record of the company itself over one of its parents."""
    for record in records:
        if (record.get("company_id") or [False])[0] == company_id:
            return record
    return records[0] if records else None


STATE_SELECTION = [
    ("received", "Received"),
    ("validated", "Validated"),
    ("processing", "Processing"),
    ("processed", "Processed"),
    ("quarantined", "Quarantined"),
    ("failed", "Failed"),
]


class SgcAccountingUpload(models.Model):
    _name = "sgc.accounting.upload"
    _description = "Accounting Document Upload"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    client_id = fields.Many2one(
        "sgc.accounting.client",
        string="Accounting Client",
        required=True,
        ondelete="cascade",
        index=True,
    )
    accounting_company_id = fields.Many2one(
        "sgc.accounting.company",
        string="Company",
        domain="[('client_id', '=', client_id)]",
        ondelete="set null",
    )
    doc_type = fields.Selection(
        DOC_TYPES, string="Document Type", required=True, tracking=True
    )
    filename = fields.Char(required=True)
    mimetype = fields.Char(string="MIME Type")
    file = fields.Binary(required=True, attachment=True)
    file_size = fields.Integer(compute="_compute_file_meta", store=True)
    file_size_human = fields.Char(compute="_compute_file_meta", store=True)
    sha256 = fields.Char(compute="_compute_file_meta", store=True, index=True)
    storage_path = fields.Char(compute="_compute_storage_path", store=True)
    state = fields.Selection(
        STATE_SELECTION,
        default="received",
        required=True,
        tracking=True,
        index=True,
    )
    doc_type_label = fields.Char(compute="_compute_labels")
    state_label = fields.Char(compute="_compute_labels")
    validation_errors = fields.Text()
    agent_run_id = fields.Char(
        string="Agent Run ID", help="UUID of the latest queued agent run."
    )
    agent_run_ids = fields.One2many(
        "sgc.accounting.agent.run",
        "upload_id",
        string="Agent Runs",
        readonly=True,
    )
    agent_state = fields.Selection(
        [
            ("queued", "Queued"),
            ("dispatched", "Dispatched"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Agent Status",
        compute="_compute_agent_state",
        store=True,
    )
    agent_state_label = fields.Char(compute="_compute_agent_state", store=True)
    row_count = fields.Integer(string="Data Rows", readonly=True)
    format_headers = fields.Text(string="Detected Headers", readonly=True)
    odoo_move_ids = fields.Text(string="Odoo Move IDs")
    uploaded_by_id = fields.Many2one(
        "res.partner",
        string="Uploaded By",
        default=lambda self: self.env.user.partner_id,
        ondelete="set null",
    )
    processed_at = fields.Datetime()
    notes = fields.Text()
    booking_state = fields.Selection(
        BOOKING_STATES,
        string="Draft Booking",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Draft booking into the client database. Empty for uploads made "
        "before per-customer booking existed.",
    )
    booking_attempts = fields.Integer(
        string="Booking Retries", readonly=True, copy=False
    )
    # Target snapshot: where this file goes, fixed once known, never changed.
    target_base_url = fields.Char(string="Target URL", readonly=True, copy=False)
    target_db = fields.Char(string="Target Database", readonly=True, copy=False)
    target_company_ref = fields.Integer(
        string="Target Company ID", readonly=True, copy=False
    )
    target_company_name = fields.Char(
        string="Target Company", readonly=True, copy=False
    )
    log_ids = fields.One2many(
        "sgc.accounting.upload.log", "upload_id", string="Log", readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("booking_state", "pending")
        uploads = super().create(vals_list)
        uploads._snapshot_target()
        for upload in uploads:
            upload._log(
                "uploaded",
                _(
                    "Uploaded by %(who)s. %(target)s",
                    who=upload.uploaded_by_id.name or "-",
                    target=upload._target_label(),
                ),
            )
        cron = self.env.ref(
            "sgc_accounting_clients.ir_cron_sgc_accounting_book_pending",
            raise_if_not_found=False,
        )
        if cron:
            cron._trigger()
        return uploads

    @api.depends("doc_type", "filename")
    def _compute_name(self):
        labels = dict(DOC_TYPES)
        for upload in self:
            upload.name = "%s - %s" % (
                labels.get(upload.doc_type, _("Document")),
                upload.filename or _("Untitled"),
            )

    @api.depends("file")
    def _compute_file_meta(self):
        for upload in self:
            raw = base64.b64decode(upload.file) if upload.file else b""
            upload.file_size = len(raw)
            upload.file_size_human = self._human_size(len(raw))
            upload.sha256 = hashlib.sha256(raw).hexdigest() if raw else False

    @api.depends(
        "client_id.client_code",
        "client_id.storage_root",
        "doc_type",
        "filename",
        "sha256",
    )
    def _compute_storage_path(self):
        for upload in self:
            if not upload.client_id or not upload.sha256:
                upload.storage_path = False
                continue
            root = (
                upload.client_id.storage_root
                or "/srv/sgc/accounting/clients"
            ).rstrip("/")
            code = upload.client_id.client_code or "client"
            doc_type = upload.doc_type or "other"
            stamp = fields.Datetime.now().strftime("%Y/%m")
            upload.storage_path = "%s/%s/inbox/%s/%s/%s_%s" % (
                root,
                code,
                doc_type,
                stamp,
                upload.sha256[:12],
                upload.filename or "document",
            )

    @api.depends("doc_type", "state")
    def _compute_labels(self):
        doc_labels = dict(DOC_TYPES)
        state_labels = dict(STATE_SELECTION)
        for upload in self:
            upload.doc_type_label = doc_labels.get(upload.doc_type, "")
            upload.state_label = state_labels.get(upload.state, "")

    @api.depends("agent_run_ids.state", "agent_run_ids.create_date")
    def _compute_agent_state(self):
        labels = dict(self._fields["agent_state"].selection)
        for upload in self:
            run = upload.agent_run_ids.sorted(
                key=lambda item: (item.create_date or fields.Datetime.now(), item.id),
                reverse=True,
            )[:1]
            upload.agent_state = run.state if run else False
            upload.agent_state_label = labels.get(run.state, "") if run else _("Not queued")

    @staticmethod
    def _human_size(size):
        value = float(size or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024.0 or unit == "GB":
                return "%.1f %s" % (value, unit)
            value /= 1024.0
        return "%d B" % (size or 0)

    @api.constrains("client_id", "accounting_company_id")
    def _check_company_client(self):
        for upload in self:
            if upload.accounting_company_id and upload.accounting_company_id.client_id != upload.client_id:
                raise ValidationError(
                    _("The selected company does not belong to this client.")
                )

    @api.constrains("file_size")
    def _check_file_size(self):
        limit = 50 * 1024 * 1024
        for upload in self:
            if upload.file_size and upload.file_size > limit:
                raise ValidationError(
                    _("The uploaded file is larger than the 50 MB limit.")
                )

    def action_mark_validated(self):
        self.write({"state": "validated", "validation_errors": False})

    def action_quarantine(self):
        self.write({"state": "quarantined"})

    def action_reset(self):
        self.write({"state": "received"})

    def action_queue_agent(self):
        """Mark an accepted upload as validated and create one agent run.

        The agent is an external service.  This method only creates the durable
        outbox record; the cron dispatcher performs the HTTP call.  This keeps
        the customer upload fast and prevents a failed agent from losing the
        document.
        """
        runs = self.env["sgc.accounting.agent.run"]
        for upload in self:
            if upload.state not in ("received", "validated"):
                continue
            existing = upload.agent_run_ids.filtered(
                lambda run: run.state in ("queued", "dispatched", "running", "completed")
            )
            if existing:
                continue
            upload.write({"state": "validated"})
            run = runs.create({"upload_id": upload.id})
            upload.write({"agent_run_id": run.run_id})
        return True

    def _assign_agent_review(self, required):
        """Ask the account manager to confirm an agent result.

        The agent never posts to the ledger.  When the deterministic gate could
        not verify the document, or when the agent proposed no confident
        match, an accountant has to confirm the result by hand.
        """
        for upload in self:
            if not required:
                continue
            reviewer = upload.client_id._reviewer()
            if not reviewer:
                continue
            activity_type = self.env.ref(
                "sgc_accounting_clients.mail_activity_type_intake_review",
                raise_if_not_found=False,
            )
            if not activity_type:
                continue
            # activity_ids holds open activities only: one review at a time.
            if upload.activity_ids.filtered(
                lambda activity: activity.activity_type_id == activity_type
            ):
                continue
            upload.activity_schedule(
                "sgc_accounting_clients.mail_activity_type_intake_review",
                user_id=reviewer.id,
                summary=_(
                    "Confirm agent result for: %(name)s", name=upload.filename or ""
                ),
                note=_(
                    "The agent produced a result that could not be verified "
                    "automatically. Check the extracted values and the proposed "
                    "matches before anything is booked."
                ),
            )
        return True

    # ------------------------------------------------------------------
    # Target snapshot and upload log
    # ------------------------------------------------------------------

    def _snapshot_target(self):
        """Record the client database and company of the upload, once.

        Empty parts are filled when they become known (a client linked after
        the upload); a recorded target is never overwritten.
        """
        for upload in self:
            client = upload.client_id
            company = upload.accounting_company_id or client.default_company_id
            values = {}
            db_name = upload.target_db or client.db_name
            if not upload.target_db and db_name:
                values["target_db"] = db_name
            # The URL may be linked after the database; take it only while the
            # client still points at the recorded database.
            if (
                not upload.target_base_url
                and client.workspace_url
                and db_name == client.db_name
            ):
                values["target_base_url"] = client.workspace_url
            if not upload.target_company_ref and company:
                values["target_company_ref"] = company.odoo_company_id
                values["target_company_name"] = company.name
            if values:
                upload.write(values)

    def _target_label(self):
        self.ensure_one()
        company = _(
            "company %(name)s (id %(id)s)",
            name=self.target_company_name or "-",
            id=self.target_company_ref or "-",
        )
        if not self.target_db:
            return _(
                "Target: %(company)s; no client database is linked yet, drafts "
                "are created once it is.",
                company=company,
            )
        return _(
            "Target: database %(db)s at %(url)s, %(company)s.",
            db=self.target_db,
            url=self.target_base_url or "-",
            company=company,
        )

    def _log(self, event, message, **values):
        self.ensure_one()
        return self.env["sgc.accounting.upload.log"].sudo().create(
            dict(
                upload_id=self.id,
                event=event,
                message=message,
                target_db=self.target_db,
                target_company_ref=self.target_company_ref,
                **values,
            )
        )

    def _booking_log_payload(self, limit=30):
        """Newest log entries, for the agent payload and prompt."""
        self.ensure_one()
        return [
            {
                "at": fields.Datetime.to_string(entry.create_date),
                "event": entry.event,
                "model": entry.record_model or "",
                "record_id": entry.record_id or False,
                "reference": entry.reference or "",
                "message": entry.message or "",
            }
            for entry in self.log_ids.sorted("id", reverse=True)[:limit]
        ]

    # ------------------------------------------------------------------
    # Draft booking into the client database (create only, never post)
    # ------------------------------------------------------------------

    @api.model
    def _cron_book_pending(self, limit=50):
        uploads = self.search(
            [("booking_state", "in", ("pending", "waiting"))],
            order="booking_state, id",
        )
        unlinked, blocked, tried = {}, set(), 0
        for upload in uploads:
            client = upload.client_id
            if client.id not in unlinked:
                unlinked[client.id] = bool(client._booking_connection()[1])
            if unlinked[client.id]:
                # No usable link here: a new upload is parked without calling
                # out, and nothing counts against the limit.
                if upload.booking_state == "waiting":
                    continue
            elif tried >= limit or client.id in blocked:
                continue
            else:
                tried += 1
            upload._book_drafts_safe()
            # Not finished means the client database is unreachable or its
            # link is broken: one attempt per client per run, so it cannot
            # hold up the other clients.
            if upload.booking_state in ("pending", "waiting"):
                blocked.add(client.id)
            # Drafts already exist remotely: keep their log even if a later
            # upload rolls this cron transaction back.
            if self.env.context.get("ir_cron_progress_id"):
                self.env["ir.cron"]._commit_progress(1)
        return True

    def action_book_drafts(self):
        # Booked or skipped uploads stay as they are; the rest are retried.
        retry = self.filtered(
            lambda upload: upload.booking_state in (False, "failed", "waiting")
        )
        retry.write({"booking_state": "pending", "booking_attempts": 0})
        retry._book_drafts_safe()
        return True

    def _book_drafts_safe(self):
        for upload in self:
            try:
                with self.env.cr.savepoint():
                    # One booking per upload at a time (cron vs. button).
                    self.env.cr.execute(
                        "SELECT booking_state FROM sgc_accounting_upload "
                        "WHERE id = %s FOR UPDATE NOWAIT",
                        [upload.id],
                    )
                    # The other side may have finished it while we waited.
                    if self.env.cr.fetchone()[0] not in ("pending", "waiting"):
                        upload.invalidate_recordset()
                        continue
                    upload._book_drafts()
            except (LockNotAvailable, SerializationFailure):
                _logger.info("Upload %s is being booked elsewhere; skipped", upload.id)
                continue
            except Exception as exc:
                _logger.exception("Draft booking failed for upload %s", upload.id)
                upload._finish("failed", rpc_error(exc))
            if upload.booking_state == "failed":
                upload.client_id._todo(
                    BOOKING_TODO,
                    _(
                        "%(file)s could not be booked into %(db)s. Its Log tab says "
                        "why; fix it and press Book Drafts.",
                        file=upload.filename,
                        db=upload.target_db or "-",
                    ),
                    record=upload,
                )
            elif upload.booking_state == "done":
                upload.activity_ids.filtered(
                    lambda activity: activity.summary == BOOKING_TODO
                ).action_feedback(feedback=_("Booked."))

    def _finish(self, state, message):
        self.booking_state = state
        self._log(state, message)

    def _wait(self, message):
        """Park the upload until the client link works (logged once)."""
        if self.booking_state != "waiting":
            self.booking_state = "waiting"
            self._log("waiting", message)

    def _stop(self, exc, prefix=""):
        """End this attempt: retry a network problem later, fail anything else."""
        message = prefix + rpc_error(exc)
        transient = isinstance(exc, (OSError, xmlrpc.client.ProtocolError))
        if transient and self.booking_attempts < BOOKING_RETRIES:
            self.booking_attempts += 1
            self.booking_state = "pending"
            self._log(
                "failed",
                _(
                    "%(error)s. Retrying at the next run (retry %(n)s of %(max)s).",
                    error=message,
                    n=self.booking_attempts,
                    max=BOOKING_RETRIES,
                ),
            )
            return None
        return self._finish(
            "failed",
            _(
                "%(error)s. Booking stopped; documents not booked yet were not "
                "created.",
                error=message,
            ),
        )

    def _book_drafts(self):
        self.ensure_one()
        if self.doc_type not in BOOKED_TYPES:
            return self._finish(
                "skipped",
                _(
                    "%(type)s documents are reviewed by hand; no draft is created.",
                    type=self.doc_type_label or self.doc_type,
                ),
            )
        self._snapshot_target()
        conn, error = self.client_id._booking_connection()
        if error:
            return self._wait(error)
        if (self.target_db, self.target_base_url) != (conn["db"], conn["url"]):
            return self._finish(
                "failed",
                _(
                    "This upload was made for %(old)s but the client is now linked "
                    "to %(new)s. Book it by hand.",
                    old="%s %s" % (self.target_base_url or "-", self.target_db),
                    new="%s %s" % (conn["url"], conn["db"]),
                ),
            )
        company_id = self.target_company_ref
        if not company_id:
            return self._finish(
                "failed", _("No company was selected for this upload.")
            )
        try:
            companies = self.client_id._verify_remote(conn, [])
        except (OSError, xmlrpc.client.ProtocolError) as exc:
            # Unreachable: nothing was created, so no retry is spent; the
            # daily check raises the to-do if it stays down.
            return self._wait(rpc_error(exc))
        except Exception as exc:
            # Revoked key or wrong role: the link needs fixing. Wait and tell
            # the reviewer; the next healthy check closes the to-do.
            self.client_id._todo(LINK_TODO, rpc_error(exc))
            return self._wait(rpc_error(exc))
        if company_id not in companies:
            # This upload's company only; the client's other uploads go on.
            return self._finish(
                "failed",
                _(
                    "The intake agent of %(db)s may not book into company id %(id)s "
                    "(%(name)s). Re-link with it, or book this file by hand.",
                    db=conn["db"],
                    id=company_id,
                    name=self.target_company_name or "-",
                ),
            )
        raw = base64.b64decode(self.file) if self.file else b""
        source = read_rows(self.doc_type, self.filename, raw, limit=MAX_UPLOAD_ROWS)
        if not source or not source["rows"]:
            return self._finish(
                "skipped",
                _("The file has no readable rows (PDF or image); review it by hand."),
            )

        context = {"allowed_company_ids": [company_id]}
        cache = {}

        def call(model, method, *args, **kwargs):
            return rpc(conn, model, method, *args, context=context, **kwargs)

        def find(model, domain, field_names=("id",), limit=1):
            key = (model, repr(domain), field_names, limit)
            if key not in cache:
                cache[key] = call(
                    model, "search_read", domain, fields=list(field_names), limit=limit
                )
            return cache[key]

        headers = source["headers"]
        try:
            self._iso_dates(headers, source["rows"])
        except ValueError as exc:
            return self._finish("failed", str(exc))
        # Every document gets a reference so a retry never books it twice; a
        # row without one gets a key from its content (see _row_key).
        seen = {}
        if self.doc_type == "payments":
            documents = [
                (_cell(headers, row, "Reference") or self._row_key(row, seen), [row])
                for row in source["rows"]
            ]
            build = self._payment_values
        else:
            # Vendor bill numbers are unique per vendor only: group by both.
            number_label, _date_label, partner_label = MOVE_COLUMNS[self.doc_type]
            grouped = {}
            for row in source["rows"]:
                number = _cell(headers, row, number_label)
                key = (
                    (_cell(headers, row, partner_label).lower(), number)
                    if number
                    else (None, self._row_key(row, seen))
                )
                grouped.setdefault(key, []).append(row)
            documents = [(key[1], rows) for key, rows in grouped.items()]
            build = self._move_values

        failed = False
        for number, (reference, rows) in enumerate(documents, 1):
            try:
                model, duplicate_domain, values, summary = build(
                    reference, rows, headers, company_id, find, number
                )
                is_move = model == "account.move"
                date_field = "invoice_date" if is_move else "date"
                existing = call(
                    model,
                    "search_read",
                    duplicate_domain,
                    fields=["id", "name", "state", "partner_id", date_field]
                    + (["narration"] if is_move else ["amount"]),
                    limit=10,
                )
                # A duplicate is this document's own draft (even after an
                # accountant corrected its date or party), or any match for
                # the same party, date and amount. Anything else conflicts.
                marker = "[SGC-DOC %s-%s]" % (self.id, number)
                match = next(
                    (r for r in existing if is_move and marker in (r.get("narration") or "")),
                    None,
                ) or next(
                    (r for r in existing if not self._conflict(r, values, date_field)), None
                )
                conflict = existing and not match and self._conflict(existing[0], values, date_field)
                if conflict:
                    # Same reference, different document (numbers restarted,
                    # or a customer PO number in ref): never book over it,
                    # never drop it silently.
                    failed = True
                    self._log(
                        "failed",
                        _(
                            "%(ref)s: %(db)s already has %(name)s with this reference, "
                            "but it %(what)s; nothing was created. If this is another "
                            "document, book it by hand.",
                            ref=reference,
                            db=self.target_db,
                            name=existing[0].get("name") or existing[0]["id"],
                            what=conflict,
                        ),
                        record_model=model,
                        record_id=existing[0]["id"],
                        reference=reference,
                    )
                    continue
                if match:
                    self._log(
                        "duplicate",
                        _(
                            "%(ref)s already exists in %(db)s as %(name)s "
                            "(%(state)s); nothing was created.",
                            ref=reference,
                            db=self.target_db,
                            name=match.get("name") or match["id"],
                            state=match.get("state") or "-",
                        ),
                        record_model=model,
                        record_id=match["id"],
                        reference=reference,
                    )
                    continue
                record_id = call(model, "create", values)
            except ValueError as exc:
                # Bad data in this document only: skip it, book the others.
                failed = True
                self._log(
                    "failed",
                    _("%(ref)s: %(error)s", ref=reference or _("Document"), error=exc),
                    reference=reference,
                )
                continue
            except Exception as exc:
                # Connection, rights or configuration: the next document
                # would fail the same way, so stop here (a retry skips the
                # drafts already created, by reference and marker).
                return self._stop(exc, "%s: " % (reference or _("Document")))
            self._log(
                "booked",
                _(
                    "%(summary)s Created as draft in %(db)s, company %(company)s.",
                    summary=summary,
                    db=self.target_db,
                    company=self.target_company_name or company_id,
                ),
                record_model=model,
                record_id=record_id,
                reference=reference,
            )
        self.booking_state = "failed" if failed else "done"
        self.booking_attempts = 0
        return None

    def _conflict(self, found, values, date_field):
        """Why a record with the same reference is not this document, if it
        isn't (a method so _() finds the language on self.env)."""
        reasons = []
        mine, theirs = values.get("partner_id"), (found.get("partner_id") or [False])[0]
        if mine and theirs and mine != theirs:
            reasons.append(_("is for another party"))
        mine, theirs = values.get(date_field), found.get(date_field)
        if mine and theirs and str(mine)[:10] != str(theirs)[:10]:
            reasons.append(_("is dated %(date)s", date=str(theirs)[:10]))
        # Two same-day partial payments may share a reference.
        mine, theirs = values.get("amount"), found.get("amount")
        if mine and theirs and round(float(mine), 2) != round(float(theirs), 2):
            reasons.append(_("is for %(amount)s", amount=theirs))
        return _(" and ").join(reasons)

    def _iso_dates(self, headers, rows):
        """Rewrite day/month/year dates (4/21/2026, 21.04.2026) in the date
        columns as YYYY-MM-DD, in place.

        Spreadsheets write dates in the order of the computer's locale, so the
        order is read from the file: a first part above 12 means day first, a
        second part above 12 means month first. A file that fits both orders,
        or neither, is refused rather than guessed: a wrong date in the books
        is worse than none.
        """
        columns = {find_column(headers, label) for label in DATE_LABELS} - {None}
        found = []
        for row in rows:
            for column in columns:
                match = DMY_DATE.match((row.get(column) or "").strip())
                if match:
                    found.append((row, column, match))
        if not found:
            return
        day_first = [m[0] for _r, _c, m in found if int(m[1]) > 12]
        month_first = [m[0] for _r, _c, m in found if int(m[2]) > 12]
        if day_first and month_first:
            raise ValueError(_(
                "This file mixes day-first dates (%(day)s) and month-first dates "
                "(%(month)s); nothing was created. Write the dates as YYYY-MM-DD "
                "and upload it again.",
                day=day_first[0], month=month_first[0],
            ))
        if not (day_first or month_first):
            raise ValueError(_(
                "Dates such as %(date)s can be read as day/month or month/day, and "
                "no date in this file settles it; nothing was created. Write the "
                "dates as YYYY-MM-DD and upload it again.",
                date=found[0][2][0],
            ))
        for row, column, match in found:
            day, month = (match[1], match[2]) if day_first else (match[2], match[1])
            try:
                row[column] = datetime.date(int(match[3]), int(month), int(day)).isoformat()
            except ValueError:
                pass  # not a real date (2/30/2026): reported with the document

    def _row_key(self, row, seen):
        """Reference for a row without one: the same row gets the same key in
        every upload of this client, so a re-sent file is not booked twice.
        Identical rows within one file stay apart by their occurrence."""
        digest = hashlib.sha256(
            repr((self.client_id.id, self.doc_type, sorted(row.items()))).encode("utf-8")
        ).hexdigest()[:12]
        seen[digest] = seen.get(digest, 0) + 1
        return "SGC-%s-%s" % (digest, seen[digest])

    def _narration(self, notes):
        return " ".join(
            [
                _(
                    "Draft from the client portal: %(file)s (upload %(id)s, "
                    "SHA-256 %(sha)s). Not posted: an accountant reviews it first.",
                    file=self.filename or "",
                    id=self.id,
                    sha=(self.sha256 or "")[:12],
                )
            ]
            + notes
        )

    def _move_values(self, reference, rows, headers, company_id, find, number):
        """One draft invoice, bill or credit note with all lines of a document."""
        _number_label, date_label, partner_label = MOVE_COLUMNS[self.doc_type]
        first = rows[0]
        if self.doc_type == "credit_notes":
            supplier = _cell(headers, first, "Party Type").lower().startswith(
                ("supplier", "vendor")
            )
            move_type = "in_refund" if supplier else "out_refund"
        elif self.doc_type == "customer_invoices":
            move_type = "out_invoice"
        else:
            move_type = "in_invoice"
        sale = move_type.startswith("out")
        journal = _own(
            find(
                "account.journal",
                [
                    ("type", "=", "sale" if sale else "purchase"),
                    ("company_id", "parent_of", company_id),
                ],
                ("id", "company_id"),
                20,
            ),
            company_id,
        )
        if not journal:
            raise UserError(
                _(
                    "Company %(company)s has no %(type)s journal",
                    company=company_id,
                    type="sale" if sale else "purchase",
                )
            )
        notes = []
        lines = []
        total = stated = 0.0
        for row in rows:
            quantity = _number(_cell(headers, row, "Quantity"), 1.0)
            price = _number(_cell(headers, row, "Unit Price"))
            tax_rate = _number(_cell(headers, row, "Tax Rate"))
            tax_amount = _number(_cell(headers, row, "Tax Amount"))
            row_total = _number(_cell(headers, row, "Total"))
            if not price and row_total and quantity:
                price = round((row_total - tax_amount) / quantity, 2)
            stated += row_total or quantity * price + tax_amount
            line = {
                "name": _cell(headers, row, "Description") or reference or self.filename,
                "quantity": quantity,
                "price_unit": price,
                # Explicit taxes only: never let the account's default tax add
                # VAT that is not in the file.
                "tax_ids": [(6, 0, [])],
            }
            tax = None
            if tax_rate:
                # ponytail: first percent tax of that rate by sequence; a chart
                # with several (reverse charge, per emirate) needs a mapping.
                tax = _own(
                    find(
                        "account.tax",
                        [
                            ("amount", "=", tax_rate),
                            ("amount_type", "=", "percent"),
                            ("type_tax_use", "=", "sale" if sale else "purchase"),
                            ("company_id", "parent_of", company_id),
                        ],
                        ("id", "company_id"),
                        20,
                    ),
                    company_id,
                )
            lines.append(line)
            # What the draft will total: Odoo computes a found tax itself,
            # otherwise only an explicit Tax Amount line adds VAT.
            total += quantity * price + (
                quantity * price * tax_rate / 100 if tax else tax_amount
            )
            if tax:
                line["tax_ids"] = [(6, 0, [tax["id"]])]
            elif tax_rate or tax_amount:
                if tax_amount:
                    lines.append(
                        {
                            "name": _("Tax %(rate)s%%", rate=tax_rate),
                            "quantity": 1.0,
                            "price_unit": tax_amount,
                            "tax_ids": [(6, 0, [])],
                        }
                    )
                note = _(
                    "No %(rate)s%% tax found: set the tax by hand before posting.",
                    rate=tax_rate,
                )
                if note not in notes:
                    notes.append(note)
        if abs(stated - total) > 0.01:
            notes.append(
                _(
                    "The file states a total of %(stated)s but the lines add up to "
                    "%(total)s; check before posting.",
                    stated=round(stated, 2),
                    total=round(total, 2),
                )
            )
        values = {
            "move_type": move_type,
            "company_id": company_id,
            "journal_id": journal["id"],
            "invoice_line_ids": [(0, 0, line) for line in lines],
        }
        if reference:
            values["ref"] = reference
        document_date = _cell(headers, first, date_label)
        if document_date:
            values["invoice_date"] = _date(document_date)
        due_date = _cell(headers, first, "Due Date")
        if due_date:
            values["invoice_date_due"] = _date(due_date)
        original = _cell(headers, first, "Original Invoice")
        if original:
            notes.append(_("Original invoice: %(ref)s.", ref=original))
        self._set_party(values, headers, first, partner_label, company_id, find, notes)
        # Marks the draft as document <number> of this upload, so a retry
        # finds its own drafts even after an accountant edited them.
        marker = "[SGC-DOC %s-%s]" % (self.id, number)
        values["narration"] = self._narration(notes + [marker])
        summary = _(
            "Draft %(type)s %(ref)s: %(lines)s line(s), total %(total)s %(currency)s.%(notes)s",
            type=MOVE_LABELS[move_type],
            ref=reference or "-",
            lines=len(rows),
            total=round(total, 2),
            currency=_cell(headers, first, "Currency"),
            notes="".join(" " + note for note in notes),
        )
        # This upload's own draft, or the same reference booked by another
        # upload. Vendor numbers are unique per vendor only, and two unknown
        # vendors of this file must not block each other.
        other = [("ref", "=", reference), ("move_type", "=", move_type)]
        if not sale:
            other += [
                ("partner_id", "=", values.get("partner_id", False)),
                ("narration", "not ilike", "[SGC-DOC %s-" % self.id),
            ]
        duplicate_domain = (
            [("company_id", "=", company_id), "|", ("narration", "ilike", marker)]
            + ["&"] * (len(other) - 1)
            + other
        )
        return "account.move", duplicate_domain, values, summary

    def _payment_values(self, reference, rows, headers, company_id, find, _index):
        """One draft payment per row."""
        row = rows[0]
        direction = _cell(headers, row, "Direction").lower()
        if direction.startswith("in"):
            payment_type, partner_type = "inbound", "customer"
        elif direction.startswith("out"):
            payment_type, partner_type = "outbound", "supplier"
        else:
            raise ValueError(
                _(
                    "Direction must be Inbound or Outbound, not %(value)r",
                    value=_cell(headers, row, "Direction"),
                )
            )
        amount = abs(_number(_cell(headers, row, "Amount")))
        if not amount:
            raise ValueError(_("the payment has no amount"))
        journals = find(
            "account.journal",
            [
                ("type", "in", ["bank", "cash"]),
                ("company_id", "parent_of", company_id),
            ],
            ("id", "name", "company_id"),
            50,
        )
        bank = _cell(headers, row, "Bank Account").lower()
        journal = next(
            (item for item in journals if bank and item["name"].lower() == bank),
            None,
        ) or _own(journals, company_id)
        if not journal:
            raise UserError(
                _("Company %(company)s has no bank journal", company=company_id)
            )
        notes = []
        values = {
            "payment_type": payment_type,
            "partner_type": partner_type,
            "amount": amount,
            "company_id": company_id,
            "journal_id": journal["id"],
        }
        if reference:
            values["memo"] = reference
        payment_date = _cell(headers, row, "Payment Date")
        if payment_date:
            values["date"] = _date(payment_date)
        invoice = _cell(headers, row, "Invoice Number")
        if invoice:
            notes.append(_("For invoice %(ref)s.", ref=invoice))
        self._set_party(values, headers, row, "Party Name", company_id, find, notes)
        summary = _(
            "Draft %(direction)s payment %(ref)s: %(amount)s %(currency)s.%(notes)s",
            direction=payment_type,
            ref=reference or "-",
            amount=amount,
            currency=_cell(headers, row, "Currency"),
            notes="".join(" " + note for note in notes),
        )
        duplicate_domain = [
            ("memo", "=", reference),
            ("payment_type", "=", payment_type),
            ("company_id", "=", company_id),
        ]
        return "account.payment", duplicate_domain, values, summary

    def _set_party(self, values, headers, row, partner_label, company_id, find, notes):
        """Add the counterparty and currency found in the client database."""
        partner_name = _cell(headers, row, partner_label)
        if partner_name:
            found = find(
                "res.partner",
                [
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "parent_of", company_id),
                    ("name", "=ilike", partner_name),
                ],
            )
            if found:
                values["partner_id"] = found[0]["id"]
            else:
                notes.append(
                    _(
                        "Counterparty %(name)s is not in the database yet; set it "
                        "on the draft.",
                        name=partner_name,
                    )
                )
        currency = _cell(headers, row, "Currency")
        if currency:
            found = find("res.currency", [("name", "=ilike", currency)])
            if not found:
                # Booking in the company currency would mislabel the amounts.
                raise ValueError(
                    _(
                        "currency %(code)s is not active in the client database",
                        code=currency,
                    )
                )
            values["currency_id"] = found[0]["id"]
