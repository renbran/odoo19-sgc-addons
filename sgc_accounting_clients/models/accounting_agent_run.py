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

from .accounting_bucket import bucket, find_column, read_rows

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
CHAT_TIMEOUT = 120


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
        return read_rows(upload.doc_type, upload.filename, data)

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

    def _build_chat_prompt(self):
        """Build the prompt sent to a chat-style agent."""
        upload = self.upload_id
        client = upload.client_id
        definition = bucket(upload.doc_type) or {}
        payload = self._build_payload()
        source = self._source_rows()
        authoritative = {"total": None, "tax": None, "net": None, "lines": 0, "errors": []}
        if source:
            authoritative = self._authoritative_totals(source["headers"], source["rows"])
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
        if source:
            context["source_headers"] = source["headers"]
            context["source_rows"] = source["rows"]
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

        The agent only extracts values and proposes matches. Every amount it
        reports is checked against the amounts parsed from the uploaded file,
        so a hallucinated total fails the run instead of reaching an
        accountant or a ledger.
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
        prompt = self._build_chat_prompt()
        source = self._source_rows()
        authoritative = {"total": None, "tax": None, "net": None, "lines": 0, "errors": []}
        if source:
            authoritative = self._authoritative_totals(source["headers"], source["rows"])
        token = self._mint_chat_token(secret, self._chat_user_id())
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-SGC-Event": "accounting.document.accepted",
            "X-SGC-Run-Id": self.run_id,
            "Authorization": "Bearer %s" % token,
        }
        body = {"prompt": prompt, "thread_id": self.id}
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
        try:
            response = requests.post(
                endpoint,
                json=body,
                headers=headers,
                timeout=CHAT_TIMEOUT,
            )
        except Exception as exc:
            self._record_failure(exc)
            raise
        attempts = (self.attempts or 0) + 1
        raw_body = (response.text or "")[:8000]
        if response.status_code < 200 or response.status_code >= 300:
            self.write(
                {
                    "attempts": attempts,
                    "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                    "response_code": response.status_code,
                    "response_body": raw_body,
                    "last_error": "HTTP %s from agent endpoint"
                    % response.status_code,
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

        try:
            result = self._parse_agent_reply(reply)
        except ValueError as exc:
            self.write(
                {
                    "attempts": attempts,
                    "state": "failed" if attempts >= MAX_ATTEMPTS else "queued",
                    "response_code": response.status_code,
                    "response_body": reply,
                    "last_error": str(exc),
                    "next_attempt_at": fields.Datetime.now()
                    + timedelta(minutes=min(2**attempts, 30)),
                }
            )
            return False

        if authoritative.get("errors"):
            self.write(
                {
                    "attempts": attempts,
                    "state": "failed",
                    "response_code": response.status_code,
                    "response_body": reply,
                    "last_error": "Source checksum mismatch: %s"
                    % "; ".join(authoritative["errors"]),
                    "next_attempt_at": False,
                    "completed_at": fields.Datetime.now(),
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
                    "last_error": str(exc),
                    "next_attempt_at": False,
                    "completed_at": fields.Datetime.now(),
                }
            )
            return False

        review_required = self._review_required(validated, authoritative)
        state = validated["state"]
        self.write(
            {
                "attempts": attempts,
                "state": state,
                "response_code": response.status_code,
                "response_body": reply,
                "matches": validated["matches"],
                "extraction": validated["extraction"],
                "review_required": review_required,
                "last_error": validated["error"] or False,
                "next_attempt_at": False,
                "completed_at": fields.Datetime.now()
                if state in ("completed", "failed")
                else False,
            }
        )
        if state == "completed":
            self.upload_id._assign_agent_review(review_required)
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
