# -*- coding: utf-8 -*-
import base64
import hashlib
import html
import logging
import os

from odoo import _, http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from werkzeug.exceptions import NotFound

from ..models.accounting_upload import DOC_TYPES

_logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"}

MESSAGES = {
    "uploaded": "Thank you. The document was received, hashed and queued for accounting.",
    "bad_file": "Please upload a PDF, CSV, XLSX, JPG or PNG file.",
    "too_large": "The file is larger than the 25 MB limit.",
    "empty": "The uploaded file is empty.",
    "bad_type": "Select a valid document type.",
    "bad_company": "Select a company that belongs to this workspace.",
    "error": "The upload could not be saved. Please try again.",
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
    def _is_internal(self, user=None):
        user = user or request.env.user
        return (
            user.has_group("base.group_system")
            or user.has_group("sgc_accounting_clients.group_sgc_accounting_user")
        )

    def _clients(self, client_code=None):
        user = request.env.user
        domain = []
        if not self._is_internal(user):
            domain.append(
                (
                    "partner_id.commercial_partner_id",
                    "=",
                    user.partner_id.commercial_partner_id.id,
                )
            )
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
        if self._is_internal():
            return True
        return (
            client.partner_id.commercial_partner_id
            == request.env.user.partner_id.commercial_partner_id
        )

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
        return request.render(
            "sgc_accounting_clients.portal_accounting_home",
            {
                "clients": self._clients(),
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
    def accounting_client(self, client_code, message=None, **kwargs):
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
        return request.render(
            "sgc_accounting_clients.portal_accounting_client",
            {
                "client": client,
                "companies": client.company_ids.filtered("active"),
                "uploads": uploads,
                "doc_types": DOC_TYPES,
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
                    }
                )
            )
            digest = hashlib.sha256(data).hexdigest()
            upload.message_post(
                body=(
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
            reviewer = client.account_manager_id
            if reviewer and not reviewer.share:
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
