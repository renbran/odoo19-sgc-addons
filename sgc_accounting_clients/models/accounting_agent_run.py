# -*- coding: utf-8 -*-
import hashlib
import hmac
import logging
import secrets
import time
import uuid
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .accounting_bucket import bucket

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


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
    match_target = fields.Json()
    payload = fields.Json()
    matches = fields.Json()
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
                _("The agent endpoint rejected the run (HTTP %s).")
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
