# -*- coding: utf-8 -*-
import base64
import hashlib
import html
import json
import logging
import os
import urllib.parse

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from werkzeug.exceptions import NotFound

from ..models.accounting_bucket import (
    BUCKETS,
    DOC_TYPES,
    MAX_UPLOAD_ROWS,
    bucket,
    read_rows,
    sample_csv,
    validate_upload_format,
)
from ..models.accounting_upload import BOOKING_STATES

# Log entries that point at a record in the owner's own database.
RECORD_EVENTS = ("booked", "duplicate", "applied")

_logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"}

MESSAGES = {
    "uploaded": "Thank you. The document was validated and queued for the accounting agent.",
    "bad_file": "Please upload a PDF, CSV, XLSX, XLS, JPG, JPEG or PNG file.",
    "too_large": "The file is larger than the 25 MB limit.",
    "empty": "The uploaded file is empty.",
    "bad_type": "Select a valid upload bucket.",
    "bad_company": "Select a company that belongs to this workspace.",
    "bad_format": "The file format does not match this bucket. Download the sample format guide and use the required columns.",
    "duplicate": "This exact file was already uploaded to this workspace. Identical files are not processed twice.",
    "error": "The upload could not be saved. Please try again.",
    "approved": "Approved. The changes are being applied to your database; this page shows the result in a minute.",
    "not_approved": "This document is not waiting for your approval.",
}


def _validate_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return "bad_file", None, None, None
    filename = os.path.basename(file_storage.filename.replace("\\", "/"))
    filename = "".join(ch for ch in filename if ch.isprintable()).strip()[:255]
    ext = os.path.splitext(filename)[1].lower()
    if not filename or ext not in ALLOWED_EXTENSIONS:
        return "bad_file", None, None, None
    data = file_storage.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        return "empty", None, None, None
    if len(data) > MAX_UPLOAD_BYTES:
        return "too_large", None, None, None
    return None, data, filename, file_storage.mimetype or "application/octet-stream"


class SgcAccountingPortal(CustomerPortal):
    def _clients(self, client_code=None):
        # A subscription has exactly one portal access: the login it was
        # registered with. Nobody else (other logins of the same company,
        # SGC staff) opens it here; staff work in the back office.
        domain = [("owner_user_id", "=", request.env.user.id)]
        if client_code:
            domain.append(("client_code", "=", client_code))
        return (
            request.env["sgc.accounting.client"]
            .sudo()
            .search(domain, order="name")
        )

    def _client_or_404(self, client_code):
        client = self._clients(client_code)[:1]
        if not client:
            raise NotFound()
        return client

    def _can_access(self, client):
        return bool(client.owner_user_id) and client.owner_user_id == request.env.user

    def _resolve_company(self, client, company_id):
        if not company_id:
            return client.default_company_id or client.company_ids[:1]
        try:
            company = request.env["sgc.accounting.company"].sudo().browse(
                int(company_id)
            )
        except (TypeError, ValueError):
            return None
        if (
            not company.exists()
            or company.client_id != client
            or not company.active
        ):
            return None
        return company

    @http.route("/my/accounting", type="http", auth="user", website=True)
    def accounting_home(self, **kwargs):
        clients = self._clients()
        # One workspace (the normal customer): skip the list, go straight to uploads.
        if len(clients) == 1:
            return request.redirect("/my/accounting/%s" % clients.client_code)
        return request.render(
            "sgc_accounting_clients.portal_accounting_home",
            {
                "clients": clients,
                "page_name": "accounting",
                "no_breadcrumbs": True,
            },
        )

    @http.route(
        "/my/accounting/<string:client_code>",
        type="http",
        auth="user",
        website=True,
    )
    def accounting_client(
        self, client_code, message=None, bucket=None, missing=None, detail=None, duplicate_of=None, **kwargs
    ):
        client = self._client_or_404(client_code)
        uploads = (
            request.env["sgc.accounting.upload"]
            .sudo()
            .search(
                [("client_id", "=", client.id)],
                order="create_date desc, id desc",
                limit=50,
            )
        )
        selected_bucket = bucket if bucket in {item["code"] for item in BUCKETS} else None
        missing_columns = [
            value.strip() for value in (missing or "").split(",") if value.strip()
        ]
        duplicate_upload = None
        if message == "duplicate" and duplicate_of:
            try:
                candidate = (
                    request.env["sgc.accounting.upload"]
                    .sudo()
                    .browse(int(duplicate_of))
                )
            except (TypeError, ValueError):
                candidate = None
            if candidate and candidate.exists() and candidate.client_id == client:
                duplicate_upload = candidate
        return request.render(
            "sgc_accounting_clients.portal_accounting_client",
            {
                "client": client,
                "client_count": len(self._clients()),
                "companies": client.company_ids.filtered("active"),
                "uploads": uploads,
                "doc_types": DOC_TYPES,
                "bucket_guides": BUCKETS,
                "selected_bucket": selected_bucket,
                "missing_columns": missing_columns,
                "format_detail": detail,
                "duplicate_upload": duplicate_upload,
                "message": _(MESSAGES[message]) if message in MESSAGES else None,
                "page_name": "accounting",
                "no_breadcrumbs": True,
            },
        )

    @http.route(
        "/my/accounting/<string:client_code>/upload",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def accounting_upload(self, client_code, **post):
        client = self._client_or_404(client_code)
        doc_type = post.get("doc_type")
        if doc_type not in dict(DOC_TYPES):
            return request.redirect(
                "/my/accounting/%s?message=bad_type" % client.client_code
            )

        error, data, filename, mimetype = _validate_upload(
            request.httprequest.files.get("file")
        )
        if error:
            return request.redirect(
                "/my/accounting/%s?message=%s" % (client.client_code, error)
            )

        format_result = validate_upload_format(doc_type, filename, data)
        if format_result.get("error"):
            query = urllib.parse.urlencode(
                {
                    "message": "bad_format",
                    "bucket": doc_type,
                    "missing": ",".join(format_result.get("missing") or []),
                    "detail": format_result.get("error") or "",
                }
            )
            return request.redirect(
                "/my/accounting/%s?%s" % (client.client_code, query)
            )

        digest = hashlib.sha256(data).hexdigest()
        duplicate = (
            request.env["sgc.accounting.upload"]
            .sudo()
            .search(
                [("client_id", "=", client.id), ("sha256", "=", digest)],
                order="create_date desc, id desc",
                limit=1,
            )
        )
        if duplicate:
            _logger.info(
                "Accounting duplicate upload blocked for client %s: upload %s "
                "matches upload %s",
                client.client_code,
                duplicate.id,
                duplicate.id,
            )
            return request.redirect(
                "/my/accounting/%s?message=duplicate&duplicate_of=%s"
                % (client.client_code, duplicate.id)
            )

        company = self._resolve_company(client, post.get("company_id"))
        if post.get("company_id") and not company:
            return request.redirect(
                "/my/accounting/%s?message=bad_company" % client.client_code
            )

        try:
            upload = (
                request.env["sgc.accounting.upload"]
                .sudo()
                .create(
                    {
                        "client_id": client.id,
                        "accounting_company_id": company.id if company else False,
                        "doc_type": doc_type,
                        "filename": filename,
                        "mimetype": mimetype,
                        "file": base64.b64encode(data),
                        "uploaded_by_id": request.env.user.partner_id.id,
                        "row_count": format_result.get("row_count") or 0,
                        "format_headers": "\n".join(
                            format_result.get("headers") or []
                        ),
                    }
                )
            )
            try:
                with request.env.cr.savepoint():
                    upload.action_queue_agent()
            except Exception:
                _logger.exception(
                    "Accounting agent queue failed for upload %s", upload.id
                )
            digest = hashlib.sha256(data).hexdigest()
            upload.message_post(                body=(
                    "<p><strong>Accounting document received</strong></p>"
                    "<ul>"
                    "<li>File: %s</li>"
                    "<li>Type: %s</li>"
                    "<li>Company: %s</li>"
                    "<li>SHA-256: <code>%s</code></li>"
                    "</ul>"
                )
                % (
                    html.escape(filename),
                    html.escape(dict(DOC_TYPES).get(doc_type, doc_type)),
                    html.escape(company.name if company else "Not specified"),
                    digest,
                ),
                author_id=request.env.user.partner_id.id,
                subtype_xmlid="mail.mt_note",
            )
            reviewer = client._reviewer()
            if reviewer:
                upload.activity_schedule(
                    "sgc_accounting_clients.mail_activity_type_intake_review",
                    user_id=reviewer.id,
                    summary=_("Review accounting document: %(name)s", name=filename),
                    note=_(
                        "Uploaded through the client portal. Verify the document, "
                        "company and SHA-256 before the agent processes it."
                    ),
                )
        except Exception:
            _logger.exception(
                "Accounting portal upload failed for client %s",
                client.client_code,
            )
            request.env.cr.rollback()
            return request.redirect(
                "/my/accounting/%s?message=error" % client.client_code
            )

        return request.redirect(
            "/my/accounting/%s?message=uploaded" % client.client_code
        )

    def _upload_or_404(self, client, upload_id):
        upload = request.env["sgc.accounting.upload"].sudo().browse(upload_id).exists()
        if not upload or upload.client_id != client:
            raise NotFound()
        return upload

    @staticmethod
    def _text(value):
        if isinstance(value, bool):
            return _("Yes") if value else _("No")
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        return str(value)

    def _agent_sections(self, extraction):
        """The agent's extraction as tables (lists of rows) and plain values."""
        sections = []
        for key, value in (extraction or {}).items():
            title = str(key).replace("_", " ").capitalize()
            if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                keys = list(dict.fromkeys(name for item in value for name in item))
                sections.append({
                    "title": title,
                    "headers": [str(name).replace("_", " ").capitalize() for name in keys],
                    "rows": [[self._text(item.get(name)) for name in keys] for item in value],
                })
            else:
                sections.append({"title": title, "text": self._text(value)})
        return sections

    @http.route(
        "/my/accounting/<string:client_code>/document/<int:upload_id>",
        type="http",
        auth="user",
        website=True,
    )
    def accounting_document(self, client_code, upload_id, message=None, **kwargs):
        client = self._client_or_404(client_code)
        upload = self._upload_or_404(client, upload_id)
        base = (upload.target_base_url or "").rstrip("/")
        logs = [
            {
                "at": log.create_date,
                "event": dict(log._fields["event"].selection).get(log.event, log.event),
                "kind": log.event,
                "reference": log.reference or "",
                "message": log.message or "",
                "url": "%s/odoo/%s/%s" % (base, log.record_model, log.record_id)
                if base and log.event in RECORD_EVENTS and log.record_model and log.record_id
                else None,
            }
            for log in upload.log_ids.sorted("id")
        ]
        run = upload.agent_run_ids.sorted("id")[-1:]
        preview = None
        if upload.booking_state == "approval" and upload.file:
            preview = read_rows(
                upload.doc_type, upload.filename, base64.b64decode(upload.file), limit=MAX_UPLOAD_ROWS
            )
        return request.render(
            "sgc_accounting_clients.portal_accounting_document",
            {
                "client": client,
                "upload": upload,
                "booking_label": dict(BOOKING_STATES).get(upload.booking_state, ""),
                "logs": logs,
                "run": run,
                "agent_sections": self._agent_sections(run.extraction) if run else [],
                "preview": preview,
                "message": _(MESSAGES[message]) if message in MESSAGES else None,
                "page_name": "accounting",
                "no_breadcrumbs": True,
            },
        )

    @http.route(
        "/my/accounting/<string:client_code>/document/<int:upload_id>/approve",
        type="http",
        auth="user",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def accounting_document_approve(self, client_code, upload_id, **post):
        client = self._client_or_404(client_code)
        upload = self._upload_or_404(client, upload_id)
        approved = upload._owner_approve(request.env.user, post.get("sha256"))
        return request.redirect(
            "/my/accounting/%s/document/%s?message=%s"
            % (client.client_code, upload.id, "approved" if approved else "not_approved")
        )

    @http.route(
        "/my/accounting/<string:client_code>/bucket/<string:bucket_code>/sample",
        type="http",
        auth="user",
        website=True,
    )
    def accounting_bucket_sample(self, client_code, bucket_code, **kwargs):
        self._client_or_404(client_code)
        if not bucket(bucket_code):
            raise NotFound()
        data = sample_csv(bucket_code)
        if not data:
            raise NotFound()
        filename = "%s_sample.csv" % bucket_code
        return request.make_response(
            data,
            headers=[
                ("Content-Type", "text/csv; charset=utf-8"),
                (
                    "Content-Disposition",
                    'attachment; filename="%s"' % filename,
                ),
                ("Cache-Control", "no-store"),
            ],
        )

    @http.route(
        "/sgc/accounting/agent/document/<int:upload_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def accounting_agent_document(self, upload_id, expires=None, token=None, **kwargs):
        runs = request.env["sgc.accounting.agent.run"].sudo()
        if not runs._verify_download_token(upload_id, expires, token):
            raise NotFound()
        upload = request.env["sgc.accounting.upload"].sudo().browse(upload_id).exists()
        if not upload:
            raise NotFound()
        raw = base64.b64decode(upload.file or b"")
        filename = (upload.filename or "document").replace('"', "").replace(
            "\r", ""
        ).replace("\n", "")
        return request.make_response(
            raw,
            headers=[
                ("Content-Type", upload.mimetype or "application/octet-stream"),
                (
                    "Content-Disposition",
                    'attachment; filename="%s"' % filename,
                ),
                ("Content-Length", str(len(raw))),
                ("Cache-Control", "no-store"),
            ],
        )

    @http.route(
        "/sgc/accounting/agent/callback",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def accounting_agent_callback(self, **kwargs):
        body = request.httprequest.get_data(cache=False)
        signature = request.httprequest.headers.get("X-SGC-Signature")
        timestamp = request.httprequest.headers.get("X-SGC-Timestamp")
        runs = request.env["sgc.accounting.agent.run"].sudo()
        if not runs._verify_callback(body, signature, timestamp):
            return request.make_response(
                json.dumps({"ok": False, "error": "invalid signature"}),
                status=403,
                headers=[("Content-Type", "application/json")],
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return request.make_response(
                json.dumps({"ok": False, "error": "invalid json"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )
        run = runs.search([("run_id", "=", payload.get("run_id"))], limit=1)
        if not run:
            return request.make_response(
                json.dumps({"ok": False, "error": "run not found"}),
                status=404,
                headers=[("Content-Type", "application/json")],
            )
        try:
            run.action_apply_callback(payload)
        except Exception as exc:
            _logger.exception("Accounting agent callback failed for %s", run.run_id)
            return request.make_response(
                json.dumps({"ok": False, "error": str(exc)}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )
        return request.make_response(
            json.dumps({"ok": True, "run_id": run.run_id, "state": run.state}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/my/accounting/upload/<int:upload_id>/download",
        type="http",
        auth="user",
        website=True,
    )
    def accounting_download(self, upload_id, **kwargs):
        upload = (
            request.env["sgc.accounting.upload"].sudo().browse(upload_id).exists()
        )
        if not upload or not self._can_access(upload.client_id):
            raise NotFound()
        raw = base64.b64decode(upload.file or b"")
        filename = (upload.filename or "document").replace('"', "")
        return request.make_response(
            raw,
            headers=[
                ("Content-Type", upload.mimetype or "application/octet-stream"),
                (
                    "Content-Disposition",
                    'attachment; filename="%s"' % filename,
                ),
                ("Content-Length", str(len(raw))),
            ],
        )
