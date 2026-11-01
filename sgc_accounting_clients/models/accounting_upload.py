# -*- coding: utf-8 -*-
import base64
import datetime
import hashlib
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .accounting_bucket import DOC_TYPES, MAX_UPLOAD_ROWS, find_column, read_rows
from .accounting_client import rpc, rpc_error

_logger = logging.getLogger(__name__)

# Buckets booked as drafts into the client database. Bank statements, payroll
# and expense receipts follow in release 2; master data and other documents
# are reviewed by hand and never become entries.
BOOKED_TYPES = ("customer_invoices", "vendor_bills", "credit_notes", "payments")
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
            reviewer = upload.client_id.account_manager_id
            if not reviewer or reviewer.share:
                continue
            activity_type = self.env.ref(
                "sgc_accounting_clients.mail_activity_type_intake_review",
                raise_if_not_found=False,
            )
            if not activity_type:
                continue
            if upload.activity_ids.filtered(
                lambda activity: activity.activity_type_id.id == activity_type.id
                and not activity.date_deadline
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
    def _cron_book_pending(self):
        uploads = self.search(
            [("booking_state", "in", ("pending", "waiting"))],
            order="booking_state, id",
            limit=50,
        )
        for upload in uploads:
            upload._book_drafts_safe()
            # Drafts already exist remotely: keep their log even if a later
            # upload rolls this cron transaction back.
            if self.env.context.get("ir_cron_progress_id"):
                self.env["ir.cron"]._commit_progress(1)
        return True

    def action_book_drafts(self):
        self.write({"booking_state": "pending"})
        self._book_drafts_safe()
        return True

    def _book_drafts_safe(self):
        for upload in self:
            try:
                with self.env.cr.savepoint():
                    upload._book_drafts()
            except Exception as exc:
                _logger.exception("Draft booking failed for upload %s", upload.id)
                upload.booking_state = "failed"
                upload._log("failed", rpc_error(exc))

    def _finish(self, state, message):
        self.booking_state = state
        self._log(state, message)

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
            if self.booking_state != "waiting":
                self.booking_state = "waiting"
                self._log("waiting", error)
            return None
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
        # Every document gets a reference so a retry never books it twice; a
        # row without one gets SGC-<upload>-<row>.
        if self.doc_type == "payments":
            documents = [
                (
                    _cell(headers, row, "Reference")
                    or "SGC-%s-%s" % (self.id, index + 1),
                    [row],
                )
                for index, row in enumerate(source["rows"])
            ]
            build = self._payment_values
        else:
            # Vendor bill numbers are unique per vendor only: group by both.
            number_label, _date_label, partner_label = MOVE_COLUMNS[self.doc_type]
            grouped = {}
            for index, row in enumerate(source["rows"]):
                number = _cell(headers, row, number_label)
                key = (
                    (_cell(headers, row, partner_label).lower(), number)
                    if number
                    else (None, "SGC-%s-%s" % (self.id, index + 1))
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
                existing = call(
                    model,
                    "search_read",
                    duplicate_domain,
                    fields=["id", "name", "state"],
                    limit=1,
                )
                if existing:
                    self._log(
                        "duplicate",
                        _(
                            "%(ref)s already exists in %(db)s as %(name)s "
                            "(%(state)s); nothing was created.",
                            ref=reference,
                            db=self.target_db,
                            name=existing[0].get("name") or existing[0]["id"],
                            state=existing[0].get("state") or "-",
                        ),
                        record_model=model,
                        record_id=existing[0]["id"],
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
                # would fail the same way, so stop here.
                failed = True
                self._log(
                    "failed",
                    _(
                        "%(ref)s: %(error)s. Booking stopped; the remaining "
                        "documents were not created.",
                        ref=reference or _("Document"),
                        error=rpc_error(exc),
                    ),
                    reference=reference,
                )
                break
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
        return None

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
