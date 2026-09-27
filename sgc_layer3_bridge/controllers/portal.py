import logging

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_MIMETYPES = {"application/pdf", "image/jpeg", "image/png"}


class Layer3Portal(CustomerPortal):
    """Billing & documents page for a Layer 3 client (linked from inside its workspace)."""

    def _l3_order(self, order_id, access_token):
        try:
            order = self._document_check_access("sale.order", order_id, access_token=access_token)
        except (AccessError, MissingError):
            return None
        return order if order.l3_tenant_slug else None

    def _l3_redirect(self, order, access_token, message):
        return request.redirect("/my/layer3/%s?access_token=%s&message=%s" % (order.id, access_token or "", message))

    @http.route("/my/layer3/<int:order_id>", type="http", auth="public", website=True)
    def l3_account(self, order_id, access_token=None, message=None, **kw):
        order = self._l3_order(order_id, access_token)
        if not order:
            return request.redirect("/my")
        messages = {
            "uploaded": _("Thank you. SGC will review your trade licence; your workspace stays fully available meanwhile."),
            "notice": _("Your notice is recorded."),
            "bad_file": _("Please upload a PDF, JPG or PNG file of at most 10 MB."),
            "bad_date": _("Please enter the licence expiry date."),
        }
        return request.render(
            "sgc_layer3_bridge.portal_layer3_account",
            {
                "order": order,
                "access_token": access_token,
                "message": messages.get(message),
                "order_url": order.get_portal_url(),
            },
        )

    @http.route("/my/layer3/<int:order_id>/documents", type="http", auth="public", methods=["POST"], website=True)
    def l3_documents(self, order_id, access_token=None, licence_file=None, licence_number=None, licence_expiry=None, **kw):
        order = self._l3_order(order_id, access_token)
        if not order:
            return request.redirect("/my")
        if not licence_file or not getattr(licence_file, "filename", None):
            return self._l3_redirect(order, access_token, "bad_file")
        data = licence_file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES or licence_file.mimetype not in ALLOWED_MIMETYPES:
            return self._l3_redirect(order, access_token, "bad_file")
        try:
            expiry = fields.Date.to_date(licence_expiry)
        except ValueError:
            expiry = None
        if not expiry:
            return self._l3_redirect(order, access_token, "bad_date")
        order._l3_submit_documents(data, licence_file.filename, licence_file.mimetype, (licence_number or "").strip()[:64], expiry)
        return self._l3_redirect(order, access_token, "uploaded")

    @http.route("/my/layer3/<int:order_id>/notice", type="http", auth="public", methods=["POST"], website=True)
    def l3_notice(self, order_id, access_token=None, confirm=None, **kw):
        order = self._l3_order(order_id, access_token)
        if not order or confirm != "yes":
            return request.redirect("/my")
        try:
            order._l3_give_notice(fields.Date.context_today(order))
        except UserError:
            _logger.info("Layer 3 notice refused for order %s", order.id)
        return self._l3_redirect(order, access_token, "notice")
