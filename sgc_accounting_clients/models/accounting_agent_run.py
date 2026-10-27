# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .accounting_bucket import MAX_UPLOAD_ROWS, bucket, find_column, read_rows

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
CHAT_TIMEOUT = 120
# Rows per chat call. Each agent reply must stay inside the response budget
# (~8k characters); 25 rows keeps it comfortably within that even for verbose
# replies, while an upload may hold up to MAX_UPLOAD_ROWS rows in total.
CHAT_BATCH_ROWS = 25


class AgentResultError(Exception):
    """Raised when an agent reply cannot be trusted.

    The error is terminal: the run fails closed instead of being retried,
    because retrying a deterministic mismatch only wastes agent calls.
    """


class SgcAccountingAgentRun(models.Model):
    _name = "sgc.accounting.agent.run"
    _description = "Accounting Document Agent Run"
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    run_id = fields.Char(
        required=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        index=True,
    )
    upload_id = fields.Many2one(
        "sgc.accounting.upload",
        string="Document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    client_id = fields.Many2one(
        "sgc.accounting.client",
        related="upload_id.client_id",
        store=True,
        index=True,
    )
    bucket = fields.Selection(
        related="upload_id.doc_type",
        store=True,
        string="Bucket",
    )
    bucket_label = fields.Char(compute="_compute_bucket_label")
    state = fields.Selection(
        [
            ("queued", "Queued"),
            ("dispatched", "Dispatched"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        default="queued",
        required=True,
        index=True,
    )
    endpoint = fields.Char()
    transport = fields.Selection(
        [
            ("event", "Event webhook"),
            ("chat", "Chat agent"),
        ],
        default="event",
        readonly=True,
        help="Transport used to reach the agent for this run.",
    )
    match_target = fields.Json()
    payload = fields.Json()
    matches = fields.Json()
    extraction = fields.Json(
        readonly=True,
        help="Structured values extracted by the agent, kept for review.",
    )
    review_required = fields.Boolean(
        readonly=True,
        help="Set when an accountant must confirm the agent result.",
    )
    workspace_move_id = fields.Char(
        readonly=True,
        help="Draft entry created in the customer workspace by this run.",
    )
    workspace_error = fields.Text(readonly=True)
    duration_seconds = fields.Integer(
        readonly=True,
        help="Seconds between the dispatch and the end of the run.",
    )
    response_code = fields.Integer()
    response_body = fields.Text()
    attempts = fields.Integer(default=0)
    last_error = fields.Text()
    next_attempt_at = fields.Datetime(default=fields.Datetime.now)
    dispatched_at = fields.Datetime()
    completed_at = fields.Datetime()
    callback_received_at = fields.Datetime()

    _run_id_uniq = models.Constraint(
        "unique(run_id)",
        "An agent run with this id already exists.",
    )

    @api.depends("upload_id.filename", "upload_id.doc_type", "run_id")
    def _compute_name(self):
        for run in self:
            filename = run.upload_id.filename or _("Document")
            run.name = "%s - %s" % (filename, (run.run_id or "")[:8])

    @api.depends("upload_id.doc_type")
    def _compute_bucket_label(self):
        for run in self:
            definition = bucket(run.upload_id.doc_type)
            run.bucket_label = definition["name"] if definition else ""

    @api.model_create_multi
    def create(self, vals_list):
        runs = super().create(vals_list)
        for run in runs:
            if run.upload_id:
                run.payload = run._build_payload()
                run.match_target = run.payload.get("match_target")
        return runs

    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    def _agent_endpoint(self):
        self.ensure_one()
        return (
            (self.client_id.agent_endpoint or "").strip()
            or (self._param("sgc_accounting_clients.agent_endpoint") or "").strip()
        )

    def _agent_token(self):
        return (self._param("sgc_accounting_clients.agent_token") or "").strip()

    def _agent_transport(self):
        """Return the transport used to reach the agent.

        ``event`` posts the JSON event to a webhook. ``chat`` posts a prompt to
        a chat-style agent such as the Odoo AI Brain orchestrator.
        """
        self.ensure_one()
        transport = (
            self._param("sgc_accounting_clients.agent_transport") or "event"
        ).strip().lower()
        return transport if transport in ("event", "chat") else "event"

    def _chat_secret(self):
        return (self._param("sgc_accounting_clients.agent_chat_secret") or "").strip()

    def _chat_user_id(self):
        raw = (self._param("sgc_accounting_clients.agent_chat_user_id") or "").strip()
        if raw:
            try:
                return int(raw)
            except ValueError:
                _logger.warning(
                    "Invalid sgc_accounting_clients.agent_chat_user_id: %s", raw
                )
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        return admin.id if admin else 1

    def _workspace_settings(self):
        """Settings of the customer workspace the agent books into."""
        params = self.env["ir.config_parameter"].sudo()
        enabled = str(
            params.get_param("sgc_accounting_clients.agent_workspace_enabled", "False")
        ).strip().lower() in ("true", "1", "yes")
        return {
            "enabled": enabled,
            "url": (
                params.get_param("sgc_accounting_clients.agent_workspace_url") or ""
            ).strip().rstrip("/"),
            "db": (
                params.get_param("sgc_accounting_clients.agent_workspace_db") or ""
            ).strip(),
            "uid": (
                params.get_param("sgc_accounting_clients.agent_workspace_user_id") or ""
            ).strip(),
            "key_file": (
                params.get_param("sgc_accounting_clients.agent_workspace_key_file") or ""
            ).strip(),
        }

    def _workspace_credentials(self):
        """Return the workspace settings and the intake agent API key."""
        settings = self._workspace_settings()
        key = ""
        if settings["key_file"]:
            try:
                with open(settings["key_file"], encoding="utf-8") as handle:
                    for line in handle:
                        if line.startswith("SGC_AGENT_API_KEY="):
                            key = line.split("=", 1)[1].strip()
            except OSError as exc:
                _logger.warning("Workspace key file unreadable: %s", exc)
        return settings, key

    def _workspace_call(self, settings, key, model, method, args=None, kwargs=None):
        """Call the customer workspace over XML-RPC with the intake agent key."""
        import xmlrpc.client

        server = xmlrpc.client.ServerProxy(
            "%s/xmlrpc/2/object" % settings["url"], allow_none=True
        )
        return server.execute_kw(
            settings["db"],
            int(settings["uid"]),
            key,
            model,
            method,
            args or [],
            kwargs or {},
        )

    def _workspace_find(self, settings, key, model, domain, fields=None, limit=1):
        records = self._workspace_call(
            settings,
            key,
            model,
            "search_read",
            [domain],
            {"fields": fields or ["id"], "limit": limit},
        )
        return records or []

    def _book_workspace_entry(self):
        """Create the draft entry in the customer workspace.

        The intake agent may create drafts, never post, so the entry lands in
        the workspace as a draft for the accountant to review.  The run records
        the created entry, or the reason why nothing was booked.
        """
        self.ensure_one()
        settings, key = self._workspace_credentials()
        if not settings["enabled"]:
            return False
        if not (settings["url"] and settings["db"] and settings["uid"] and key):
            self.write(
                {
                    "workspace_error": _(
                        "The workspace booking is enabled but not configured."
                    )
                }
            )
            return False
        upload = self.upload_id
        bucket_code = upload.doc_type
        if bucket_code not in ("customer_invoices", "vendor_bills"):
            self.write(
                {
                    "workspace_error": _(
                        "Bucket %(bucket)s is not booked automatically."
                    )
                    % {"bucket": bucket_code}
                }
            )
            return False
        source = self._source_rows()
        if not source or not source["rows"]:
            self.write(
                {"workspace_error": _("There are no source rows to book.")}
            )
            return False
        row = source["rows"][0]
        headers = source["headers"]

        def value(*labels):
            for label in labels:
                column = find_column(headers, label)
                if column:
                    raw = (row.get(column) or "").strip()
                    if raw:
                        return raw
            return ""

        def number(raw, default=0.0):
            try:
                return float(str(raw).replace(",", ""))
            except (TypeError, ValueError):
                return default

        reference = value("Invoice Number", "Bill Number", "Reference", "Document Number")
        invoice_date = value("Invoice Date", "Bill Date", "Date")
        due_date = value("Due Date", "Payment Due Date")
        partner_name = value(
            "Customer Name", "Vendor Name", "Supplier Name", "Partner Name"
        )
        currency_name = value("Currency")
        description = value("Description", "Particulars", "Narration")
        quantity = number(value("Quantity", "Qty"), 1.0)
        unit_price = number(value("Unit Price", "Price", "Rate"))
        tax_amount = number(value("Tax Amount", "VAT Amount"))
        tax_rate = number(value("Tax Rate", "VAT Rate"), 0.0)
        total = number(value("Total", "Total Amount", "Amount"))
        if not unit_price and total and quantity:
            unit_price = round(total / quantity, 2)

        try:
            partner_id = False
            counterparty_note = ""
            if partner_name:
                found = self._workspace_find(
                    settings,
                    key,
                    "res.partner",
                    [("name", "=ilike", partner_name)],
                    ["id"],
                )
                if found:
                    partner_id = found[0]["id"]
                else:
                    counterparty_note = _(
                        " The counterparty %(name)s is not in the workspace yet, "
                        "so the accountant must set it on the draft."
                    ) % {"name": partner_name}
            currency_id = False
            if currency_name:
                found = self._workspace_find(
                    settings,
                    key,
                    "res.currency",
                    [("name", "=ilike", currency_name)],
                    ["id"],
                )
                currency_id = found[0]["id"] if found else False
            journal_type = "sale" if bucket_code == "customer_invoices" else "purchase"
            journals = self._workspace_find(
                settings,
                key,
                "account.journal",
                [("type", "=", journal_type)],
                ["id"],
            )
            if not journals:
                self.write(
                    {
                        "workspace_error": _(
                            "The workspace has no %(type)s journal."
                        )
                        % {"type": journal_type}
                    }
                )
                return False
            tax_id = False
            if tax_rate:
                taxes = self._workspace_find(
                    settings,
                    key,
                    "account.tax",
                    [("amount", "=", tax_rate)],
                    ["id"],
                )
                tax_id = taxes[0]["id"] if taxes else False
            lines = [
                {
                    "name": description or reference or "Document",
                    "quantity": quantity,
                    "price_unit": unit_price,
                }
            ]
            if tax_id:
                lines[0]["tax_ids"] = [(6, 0, [tax_id])]
            elif tax_amount:
                lines.append(
                    {
                        "name": _("Tax %(rate)s%%")
                        % {"rate": tax_rate or 0},
                        "quantity": 1.0,
                        "price_unit": tax_amount,
                    }
                )
            values = {
                "move_type": (
                    "out_invoice"
                    if bucket_code == "customer_invoices"
                    else "in_invoice"
                ),
                "journal_id": journals[0]["id"],
                "invoice_line_ids": [(0, 0, line) for line in lines],
                "narration": _(
                    "Booked from the client portal by %(run)s. Source: %(name)s "
                    "(SHA-256 %(sha)s).%(note)s"
                )
                % {
                    "run": self.name,
                    "name": upload.filename or "",
                    "sha": upload.sha256 or "",
                    "note": counterparty_note,
                },
            }
            if partner_id:
                values["partner_id"] = partner_id
            if currency_id:
                values["currency_id"] = currency_id
            if reference:
                values["ref"] = reference
            if invoice_date:
                values["invoice_date"] = invoice_date
            if due_date:
                values["invoice_date_due"] = due_date
            move_id = self._workspace_call(
                settings, key, "account.move", "create", [values]
            )
        except Exception as exc:
            self.write({"workspace_error": str(exc)[:2000]})
            _logger.exception("Workspace booking failed for run %s", self.run_id)
            return False
        self.write({"workspace_move_id": str(move_id), "workspace_error": False})
        upload.write(
            {
                "odoo_move_ids": "%s|%s" % (settings["url"], move_id),
                "notes": _(
                    "Draft entry %(move)s created in the workspace by agent run "
                    "%(run)s. It is not posted: an accountant reviews it first."
                )
                % {"move": move_id, "run": self.name},
            }
        )
        return True

    def _mint_chat_token(self, secret, user_id, ttl=300):
        """Mint a short-lived HS256 token for the chat agent."""
        def encode(raw):
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

        header = encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        now = int(time.time())
        claims = encode(
            json.dumps(
                {"sub": str(user_id), "iat": now, "exp": now + ttl},
                separators=(",", ":"),
            ).encode("utf-8")
        )
        signing = "%s.%s" % (header, claims)
        signature = encode(
            hmac.new(
                secret.encode("utf-8"), signing.encode("ascii"), hashlib.sha256
            ).digest()
        )
        return "%s.%s" % (signing, signature)

    def _source_rows(self):
        """Return the authoritative source rows of a tabular upload."""
        upload = self.upload_id
        try:
            data = upload.file
        except Exception:  # pragma: no cover - defensive
            return None
        if not data:
            return None
        try:
            raw = base64.b64decode(data)
        except Exception:
            raw = data if isinstance(data, bytes) else b""
        return read_rows(
            upload.doc_type, upload.filename, raw, limit=MAX_UPLOAD_ROWS
        )

    def _authoritative_totals(self, headers, rows):
        """Compute the totals the agent must agree with.

        The values come from the uploaded file, never from the agent, so a
        hallucinated amount cannot pass the gate.
        """
        empty = {"total": None, "tax": None, "net": None, "lines": 0, "errors": []}
        if not headers or not rows:
            return empty
        quantity = find_column(headers, "Quantity")
        unit_price = find_column(headers, "Unit Price")
        tax_amount = find_column(headers, "Tax Amount")
        total_column = find_column(headers, "Total") or find_column(headers, "Amount")
        errors = []
        net = 0.0
        tax_total = 0.0
        stated_total = 0.0
        has_stated = False

        def to_float(value):
            if value is None or value == "":
                return 0.0
            try:
                return float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                raise ValueError("non numeric amount")

        for row in rows:
            try:
                qty = to_float(row.get(quantity)) if quantity else 0.0
                price = to_float(row.get(unit_price)) if unit_price else 0.0
                tax = to_float(row.get(tax_amount)) if tax_amount else 0.0
                stated = (
                    to_float(row.get(total_column)) if total_column else None
                )
            except ValueError:
                errors.append("A row contains an amount that is not a number.")
                break
            net += qty * price
            tax_total += tax
            if stated is not None:
                has_stated = True
                stated_total += stated
                if quantity and unit_price and abs((qty * price + tax) - stated) > 0.01:
                    errors.append(
                        "A row states %s but quantity x unit price plus tax is %s."
                        % (stated, round(qty * price + tax, 2))
                    )
        if errors:
            return {"total": None, "tax": None, "net": None, "lines": len(rows), "errors": errors}
        return {
            "total": round(stated_total, 2) if has_stated else round(net + tax_total, 2),
            "tax": round(tax_total, 2) if tax_amount else None,
            "net": round(net, 2),
            "lines": len(rows),
            "errors": [],
        }

    def _build_chat_prompt(self, headers, rows, authoritative, batch_note=None):
        """Build the prompt sent to a chat-style agent for one batch."""
        upload = self.upload_id
        client = upload.client_id
        definition = bucket(upload.doc_type) or {}
        payload = self._build_payload()
        context = {
            "client": {"code": client.client_code, "name": client.name},
            "bucket": {
                "code": upload.doc_type,
                "label": definition.get("name", upload.doc_type),
                "required_columns": list(definition.get("required", ())),
            },
            "document": {
                "filename": upload.filename,
                "mimetype": upload.mimetype or "",
                "sha256": upload.sha256,
                "size": upload.file_size,
                "row_count": upload.row_count,
                "download_url": payload["document"]["download_url"],
            },
            "match_target": payload["match_target"],
            "policy": payload["policy"],
            "authoritative_totals": authoritative,
        }
        if rows:
            context["source_headers"] = headers
            context["source_rows"] = rows
            if batch_note:
                context["batch_note"] = batch_note
        return "\n".join(
            [
                "You are the intake agent of an accounting firm that books client "
                "documents into Odoo.",
                "Read the CONTEXT block below and return one JSON object. No prose, "
                "no markdown.",
                "",
                "CONTEXT:",
                json.dumps(context, ensure_ascii=False, default=str, indent=2),
                "",
                "RULES:",
                "1. Use only the values in source_rows. Never invent amounts, dates, "
                "parties or tax values.",
                "2. If source_rows is present, any total you report must equal "
                "authoritative_totals.total within 0.01.",
                "3. matches are candidate records found in source_rows, each with "
                "reference, counterparty, total, currency and a confidence between "
                "0 and 1. Use an empty list when there is no candidate.",
                "4. If source_rows is missing or unreadable, return state \"failed\" "
                "and explain why in error.",
                "5. Never post or create accounting entries. You only extract values "
                "and propose matches for an accountant to review.",
                "",
                "RETURN EXACTLY THIS JSON SHAPE:",
                '{"state": "completed", "matches": [{"reference": "", '
                '"counterparty": "", "total": 0.0, "currency": "", '
                '"confidence": 0.0, "trn": ""}], "extraction": {}, "error": ""}',
            ]
        )

    def _parse_agent_reply(self, text):
        """Return the JSON object contained in an agent reply."""
        if not text:
            raise ValueError("The agent returned an empty reply.")
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```[a-zA-Z]*", "", candidate)
            candidate = re.sub(r"```$", "", candidate).strip()
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("The agent reply did not contain a JSON object.")
        try:
            data = json.loads(candidate[start:end + 1])
        except ValueError as exc:
            raise ValueError("The agent reply is not valid JSON: %s" % exc) from exc
        if not isinstance(data, dict):
            raise ValueError("The agent reply is not a JSON object.")
        return data

    def _validate_agent_result(self, result, authoritative):
        """Validate an agent result and apply the deterministic gate."""
        state = str(result.get("state") or "").strip().lower()
        if state not in ("completed", "failed"):
            raise AgentResultError(
                "The agent returned an unsupported state: %s" % (state or "missing")
            )
        extraction = result.get("extraction")
        if not isinstance(extraction, dict):
            extraction = {}
        raw_matches = result.get("matches")
        if raw_matches is None:
            raw_matches = []
        if not isinstance(raw_matches, list):
            raise AgentResultError("The agent returned a matches value that is not a list.")

        expected_total = authoritative.get("total")
        matches = []
        for match in raw_matches:
            if not isinstance(match, dict):
                continue
            try:
                confidence = float(match.get("confidence"))
            except (TypeError, ValueError):
                continue
            if confidence < 0 or confidence > 1:
                continue
            try:
                total = float(match.get("total"))
            except (TypeError, ValueError):
                total = None
            if (
                total is not None
                and expected_total is not None
                and abs(total - expected_total) > 0.01
            ):
                raise AgentResultError(
                    "Checksum mismatch: the agent proposed a total of %s but the "
                    "source totals %s." % (total, expected_total)
                )
            matches.append(
                {
                    "reference": str(match.get("reference") or "").strip(),
                    "counterparty": str(match.get("counterparty") or "").strip(),
                    "total": total,
                    "currency": str(match.get("currency") or "").strip(),
                    "confidence": confidence,
                    "trn": str(match.get("trn") or "").strip(),
                }
            )
        if state == "completed" and expected_total is not None:
            reported = extraction.get("total")
            if reported is not None:
                try:
                    reported = float(reported)
                except (TypeError, ValueError):
                    reported = None
                if reported is not None and abs(reported - expected_total) > 0.01:
                    raise AgentResultError(
                        "Checksum mismatch: the agent reported a document total of "
                        "%s but the source totals %s." % (reported, expected_total)
                    )
        return {
            "state": state,
            "matches": matches,
            "extraction": extraction,
            "error": str(result.get("error") or "").strip(),
        }

    def _review_required(self, validated, authoritative):
        """Return True when an accountant must confirm the agent result."""
        client = self.client_id
        if authoritative.get("total") is None:
            return True
        if not validated["matches"]:
            return True
        minimum = client.min_confidence or 0.0
        for match in validated["matches"]:
            if match["confidence"] < minimum:
                return True
        if client.require_trn:
            for match in validated["matches"]:
                if not match.get("trn"):
                    return True
        return False

    def _portal_base_url(self):
        base = (self._param("web.base.url") or "").strip().rstrip("/")
        if not base:
            base = "https://app.sgctech.ai"
        return base

    def _download_secret(self):
        params = self.env["ir.config_parameter"].sudo()
        secret = params.get_param("sgc_accounting_clients.agent_download_secret")
        if not secret:
            secret = secrets.token_urlsafe(32)
            params.set_param("sgc_accounting_clients.agent_download_secret", secret)
        return secret

    def _download_token(self, upload_id, expires):
        message = "%s:%s" % (upload_id, expires)
        return hmac.new(
            self._download_secret().encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _verify_download_token(self, upload_id, expires, token):
        try:
            expires = int(expires)
        except (TypeError, ValueError):
            return False
        if expires < int(time.time()):
            return False
        expected = self._download_token(upload_id, expires)
        return hmac.compare_digest(expected, token or "")

    def _build_payload(self):
        self.ensure_one()
        upload = self.upload_id
        client = upload.client_id
        definition = bucket(upload.doc_type) or {}
        expires = int(time.time()) + 24 * 60 * 60
        base = self._portal_base_url()
        token = self._download_token(upload.id, expires)
        download_url = "%s/sgc/accounting/agent/document/%s?expires=%s&token=%s" % (
            base,
            upload.id,
            expires,
            token,
        )
        sample_url = "%s/my/accounting/%s/bucket/%s/sample" % (
            base,
            client.client_code,
            upload.doc_type,
        )
        return {
            "version": "1.0",
            "event": "accounting.document.accepted",
            "run_id": self.run_id,
            "created_at": fields.Datetime.now().isoformat(),
            "agent": client.assigned_agent or "agent-00",
            "source": "app.sgctech.ai",
            "client": {
                "id": client.id,
                "code": client.client_code,
                "name": client.name,
                "partner_id": client.partner_id.id,
                "workspace_url": client.workspace_url or "",
            },
            "bucket": {
                "code": upload.doc_type,
                "label": definition.get("name", upload.doc_type),
                "required_columns": list(definition.get("required", ())),
                "sample_url": sample_url,
            },
            "document": {
                "upload_id": upload.id,
                "filename": upload.filename,
                "mimetype": upload.mimetype or "",
                "sha256": upload.sha256,
                "size": upload.file_size,
                "row_count": upload.row_count,
                "download_url": download_url,
                "expires_at": expires,
            },
            "match_target": {
                "engine": "odoo",
                "url": client.workspace_url or "",
                "db_name": client.db_name or "",
                "company_ids": [
                    company.odoo_company_id
                    for company in client.company_ids
                    if company.active
                ],
                "default_company_id": (
                    client.default_company_id.odoo_company_id
                    if client.default_company_id
                    else False
                ),
                "mode": "read_only",
            },
            "policy": {
                "auto_post_max_aed": client.auto_post_max_aed,
                "min_confidence": client.min_confidence,
                "require_trn": client.require_trn,
                "posting_allowed": False,
            },
            "callback": {
                "url": "%s/sgc/accounting/agent/callback" % base,
                "signature_header": "X-SGC-Signature",
                "timestamp_header": "X-SGC-Timestamp",
                "signature_format": "HMAC-SHA256('<timestamp>.<raw body>')",
                "tolerance_seconds": 300,
            },
        }

    def _run_duration(self):
        """Seconds between the dispatch and the end of this run."""
        self.ensure_one()
        if not (self.dispatched_at and self.completed_at):
            return 0
        return int((self.completed_at - self.dispatched_at).total_seconds())

    def _record_failure(self, exc):
        self.ensure_one()
        attempts = (self.attempts or 0) + 1
        values = {
            "attempts": attempts,
            "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
            "last_error": str(exc)[:4000],
            "next_attempt_at": fields.Datetime.now()
            + timedelta(minutes=min(2**attempts, 30)),
        }
        self.write(values)

    def _send(self, endpoint):
        """Dispatch the run to the agent using the configured transport."""
        self.ensure_one()
        if self._agent_transport() == "chat":
            return self._send_chat(endpoint)
        return self._send_event(endpoint)

    def _send_event(self, endpoint):
        self.ensure_one()
        payload = self._build_payload()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-SGC-Event": "accounting.document.accepted",
            "X-SGC-Run-Id": self.run_id,
        }
        token = self._agent_token()
        if token:
            headers["Authorization"] = "Bearer %s" % token
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - Odoo image has requests
            raise UserError(_("The requests library is not available.")) from exc
        self.write(
            {
                "payload": payload,
                "match_target": payload.get("match_target"),
                "endpoint": endpoint,
                "transport": "event",
                "state": "dispatched",
                "dispatched_at": fields.Datetime.now(),
            }
        )
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=20,
            )
        except Exception as exc:
            self._record_failure(exc)
            raise
        body = (response.text or "")[:8000]
        attempts = (self.attempts or 0) + 1
        if response.status_code < 200 or response.status_code >= 300:
            self.write(
                {
                    "attempts": attempts,
                    "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                    "response_code": response.status_code,
                    "response_body": body,
                    "last_error": "HTTP %s from agent endpoint"
                    % response.status_code,
                    "next_attempt_at": fields.Datetime.now()
                    + timedelta(minutes=min(2**attempts, 30)),
                }
            )
            return False
        self.write(
            {
                "attempts": attempts,
                "state": "dispatched",
                "response_code": response.status_code,
                "response_body": body,
                "last_error": False,
                "next_attempt_at": False,
            }
        )
        return True

    def _send_chat(self, endpoint):
        """Send the run to a chat-style agent and apply the result.

        The source rows are processed in batches of ``CHAT_BATCH_ROWS``: one
        chat call per batch, each checked against the authoritative totals of
        its own slice. This keeps every agent reply well inside the response
        budget, so large documents no longer depend on the agent echoing an
        oversized JSON blob. The agent only extracts values and proposes
        matches; every amount it reports is checked against the amounts parsed
        from the uploaded file, so a hallucinated total fails the run instead
        of reaching an accountant or a ledger.
        """
        self.ensure_one()
        secret = self._chat_secret()
        if not secret:
            raise UserError(
                _(
                    "The chat agent secret is not configured. Set the system "
                    "parameter sgc_accounting_clients.agent_chat_secret."
                )
            )
        try:
            import requests
        except ImportError as exc:  # pragma: no cover - Odoo image has requests
            raise UserError(_("The requests library is not available.")) from exc

        payload = self._build_payload()
        source = self._source_rows()
        if source:
            headers = source["headers"]
            all_rows = list(source["rows"])
        else:
            headers = None
            all_rows = []
        batches = [
            all_rows[index : index + CHAT_BATCH_ROWS]
            for index in range(0, len(all_rows), CHAT_BATCH_ROWS)
        ] or [[]]
        total_batches = len(batches)
        token = self._mint_chat_token(secret, self._chat_user_id())
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-SGC-Event": "accounting.document.accepted",
            "X-SGC-Run-Id": self.run_id,
            "Authorization": "Bearer %s" % token,
        }
        self.write(
            {
                "payload": payload,
                "match_target": payload.get("match_target"),
                "endpoint": endpoint,
                "transport": "chat",
                "state": "dispatched",
                "dispatched_at": fields.Datetime.now(),
            }
        )
        attempts = (self.attempts or 0) + 1
        matches = []
        extraction = {}
        last_reply = ""
        merged_total = 0.0
        merged_tax = 0.0
        merged_net = 0.0
        has_total = has_tax = has_net = False
        merged_lines = 0

        for index, batch_rows in enumerate(batches, start=1):
            if source:
                authoritative = self._authoritative_totals(headers, batch_rows)
                if authoritative.get("errors"):
                    self.write(
                        {
                            "attempts": attempts,
                            "state": "failed",
                            "last_error": "Source checksum mismatch in batch "
                            "%s/%s: %s"
                            % (index, total_batches, "; ".join(authoritative["errors"])),
                            "next_attempt_at": False,
                            "completed_at": fields.Datetime.now(),
                        }
                    )
                    return False
            else:
                authoritative = {"total": None, "tax": None, "net": None, "lines": 0, "errors": []}
            batch_note = None
            if total_batches > 1:
                batch_note = (
                    "This document is processed in %s batches and this is batch "
                    "%s of %s. Only the rows in source_rows belong to this "
                    "batch." % (total_batches, index, total_batches)
                )
            prompt = self._build_chat_prompt(headers, batch_rows, authoritative, batch_note)
            thread_id = (
                "%s.%s" % (self.run_id, index) if total_batches > 1 else self.id
            )
            body = {"prompt": prompt, "thread_id": thread_id}
            try:
                response = requests.post(
                    endpoint,
                    json=body,
                    headers=request_headers,
                    timeout=CHAT_TIMEOUT,
                )
            except Exception as exc:
                self.write(
                    {
                        "attempts": attempts,
                        "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                        "last_error": "batch %s/%s: %s"
                        % (index, total_batches, str(exc)[:1000]),
                        "next_attempt_at": fields.Datetime.now()
                        + timedelta(minutes=min(2**attempts, 30)),
                    }
                )
                return False
            raw_body = (response.text or "")[:8000]
            if response.status_code < 200 or response.status_code >= 300:
                self.write(
                    {
                        "attempts": attempts,
                        "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                        "response_code": response.status_code,
                        "response_body": raw_body,
                        "last_error": "batch %s/%s: HTTP %s from agent endpoint"
                        % (index, total_batches, response.status_code),
                        "next_attempt_at": fields.Datetime.now()
                        + timedelta(minutes=min(2**attempts, 30)),
                    }
                )
                return False

            reply = raw_body
            try:
                data = response.json()
            except ValueError:
                data = {}
            if isinstance(data, dict) and data.get("reply"):
                reply = str(data["reply"])[:8000]
            last_reply = reply

            try:
                result = self._parse_agent_reply(reply)
            except ValueError as exc:
                self.write(
                    {
                        "attempts": attempts,
                        "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                        "response_code": response.status_code,
                        "response_body": reply,
                        "last_error": "batch %s/%s: %s"
                        % (index, total_batches, exc),
                        "next_attempt_at": fields.Datetime.now()
                        + timedelta(minutes=min(2**attempts, 30)),
                    }
                )
                return False

            try:
                validated = self._validate_agent_result(result, authoritative)
            except AgentResultError as exc:
                self.write(
                    {
                        "attempts": attempts,
                        "state": "failed",
                        "response_code": response.status_code,
                        "response_body": reply,
                        "last_error": "batch %s/%s: %s"
                        % (index, total_batches, exc),
                        "next_attempt_at": False,
                        "completed_at": fields.Datetime.now(),
                    }
                )
                return False

            matches.extend(validated["matches"])
            extraction.update(validated["extraction"] or {})
            if authoritative.get("total") is not None:
                has_total = True
                merged_total += authoritative["total"]
            if authoritative.get("tax") is not None:
                has_tax = True
                merged_tax += authoritative["tax"]
            if authoritative.get("net") is not None:
                has_net = True
                merged_net += authoritative["net"]
            merged_lines += authoritative.get("lines") or 0

        merged = {
            "total": round(merged_total, 2) if has_total else None,
            "tax": round(merged_tax, 2) if has_tax else None,
            "net": round(merged_net, 2) if has_net else None,
            "lines": merged_lines,
            "errors": [],
        }
        state = result.get("state") or "completed"
        state = str(state).strip().lower()
        if state not in ("completed", "failed"):
            state = "failed"
        review_required = self._review_required(
            {"matches": matches}, merged
        )
        finished_at = fields.Datetime.now()
        duration = 0
        if self.dispatched_at:
            duration = int((finished_at - self.dispatched_at).total_seconds())
        self.write(
            {
                "attempts": attempts,
                "state": state,
                "response_code": response.status_code,
                "response_body": last_reply,
                "matches": matches,
                "extraction": extraction,
                "review_required": review_required,
                "last_error": False,
                "next_attempt_at": False,
                "completed_at": finished_at
                if state in ("completed", "failed")
                else False,
                "duration_seconds": duration,
            }
        )
        if state == "completed":
            self.upload_id._assign_agent_review(review_required)
            self._book_workspace_entry()
        return True

    def action_dispatch(self):
        self.ensure_one()
        endpoint = self._agent_endpoint()
        if not endpoint:
            raise UserError(
                _(
                    "No agent endpoint is configured. Set it on the client "
                    "(Automation tab) or in the system parameter "
                    "sgc_accounting_clients.agent_endpoint."
                )
            )
        try:
            sent = self._send(endpoint)
        except Exception as exc:
            raise UserError(_("Agent dispatch failed: %s") % exc) from exc
        if not sent:
            raise UserError(
                self.last_error
                or _("The agent endpoint rejected the run (HTTP %s).")
                % (self.response_code or "?")
            )
        return True

    def action_retry(self):
        self.write(
            {
                "state": "queued",
                "next_attempt_at": fields.Datetime.now(),
                "last_error": False,
            }
        )
        return True

    @api.model
    def _cron_dispatch_queued(self):
        runs = self.search(
            [
                ("state", "=", "queued"),
                ("next_attempt_at", "<=", fields.Datetime.now()),
            ],
            limit=20,
            order="next_attempt_at, id",
        )
        for run in runs:
            endpoint = run._agent_endpoint()
            if not endpoint:
                run.write(
                    {
                        "last_error": _(
                            "No agent endpoint is configured for this client."
                        ),
                        "next_attempt_at": fields.Datetime.now() + timedelta(hours=1),
                    }
                )
                continue
            try:
                run._send(endpoint)
            except Exception:
                _logger.exception(
                    "Accounting agent dispatch failed for run %s", run.run_id
                )
        return True

    @api.model
    def _verify_callback(self, body, signature, timestamp=None):
        secret = self._param("sgc_accounting_clients.agent_callback_secret")
        if not secret:
            return False
        try:
            stamp = int(timestamp)
        except (TypeError, ValueError):
            return False
        if abs(int(time.time()) - stamp) > 300:
            return False
        message = ("%s." % stamp).encode("utf-8") + body
        expected = hmac.new(
            secret.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        supplied = (signature or "").strip()
        if supplied.startswith("sha256="):
            supplied = supplied[7:]
        if supplied.startswith("v1="):
            supplied = supplied[3:]
        return hmac.compare_digest(expected, supplied)

    def action_apply_callback(self, values):
        """Apply a validated callback from the external agent."""
        self.ensure_one()
        state = values.get("state")
        if state not in ("running", "completed", "failed", "cancelled"):
            raise UserError(_("Invalid agent callback state."))
        update = {
            "state": state,
            "last_error": values.get("error") or False,
            "callback_received_at": fields.Datetime.now(),
        }
        if values.get("matches") is not None:
            update["matches"] = values["matches"]
        if values.get("response") is not None:
            update["response_body"] = str(values["response"])[:8000]
        if state in ("completed", "failed", "cancelled"):
            update["completed_at"] = fields.Datetime.now()
        self.write(update)
        return True
