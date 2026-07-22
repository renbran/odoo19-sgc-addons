# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

SECRET_PARAM_KEY = "sgc_cip_bridge.webhook_secret"


class CipWebhookController(http.Controller):
    """Receives priced proposals pushed from CIP and creates a sale.order.

    Plain HTTP + JSON body (not Odoo's `type="json"` JSON-RPC envelope)
    so a non-Odoo caller (a FastAPI service) can POST a normal JSON
    payload without wrapping it in `{"jsonrpc": "2.0", "method": "call",
    "params": {...}}`.
    """

    @http.route(
        "/cip-webhook/proposal-push",
        type="http",
        auth="public",
        csrf=False,
        methods=["POST"],
    )
    def push_proposal(self, **kwargs):
        def _json_response(payload, status=200):
            return Response(json.dumps(payload), status=status, content_type="application/json")

        expected_secret = request.env["ir.config_parameter"].sudo().get_param(SECRET_PARAM_KEY)
        provided_secret = request.httprequest.headers.get("X-CIP-Webhook-Secret")
        if not expected_secret or provided_secret != expected_secret:
            _logger.warning(
                "Rejected CIP webhook call from %s: invalid or missing secret",
                request.httprequest.remote_addr,
            )
            return _json_response({"status": "error", "message": "Unauthorized"}, status=401)

        try:
            payload = request.httprequest.get_json(force=True)
        except Exception:
            return _json_response({"status": "error", "message": "Invalid JSON body"}, status=400)

        proposal_id = payload.get("proposal_id")
        title = payload.get("title")
        currency_code = payload.get("currency", "AED")
        total_value = payload.get("total_value")
        customer_name = payload.get("customer_name")
        customer_email = payload.get("customer_email")

        if not title or total_value is None or not customer_name:
            return _json_response(
                {"status": "error", "message": "Missing required fields: title, total_value, customer_name"},
                status=400,
            )

        env = request.env
        partner_model = env["res.partner"].sudo()
        partner = None
        if customer_email:
            partner = partner_model.search([("email", "=", customer_email)], limit=1)
        if not partner:
            partner = partner_model.search([("name", "=", customer_name)], limit=1)
        if not partner:
            partner = partner_model.create({"name": customer_name, "email": customer_email or False})

        currency = env["res.currency"].sudo().search([("name", "=", currency_code)], limit=1)

        line_vals = {
            "name": title,
            "product_uom_qty": 1,
            "price_unit": total_value,
        }
        product = env.ref("sgc_cip_bridge.product_cip_consulting_service", raise_if_not_found=False)
        if product:
            line_vals["product_id"] = product.id

        order_vals = {
            "partner_id": partner.id,
            "origin": f"CIP-{proposal_id}" if proposal_id else "CIP",
            "order_line": [(0, 0, line_vals)],
        }
        if currency:
            order_vals["currency_id"] = currency.id

        order = env["sale.order"].sudo().create(order_vals)

        _logger.info(
            "CIP webhook created sale.order %s (id=%s) for proposal_id=%s",
            order.name,
            order.id,
            proposal_id,
        )

        return _json_response({"status": "success", "order_id": order.id, "order_ref": order.name})
