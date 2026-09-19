import logging

from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Must stay in sync with kartatap's src/lib/tier.ts TIERS and MIN_SEATS.
_PLAN_MIN_QUANTITY = {"SOLO": 1, "TEAM": 2, "BUSINESS": 2}
_KARTATAP_COMPANY_ID = 10  # res.company id for "KartaTap" (fixed; not configurable via RPC input)


class KartatapCheckout(models.AbstractModel):
    """The Odoo-side counterpart to KartaTap's POST /api/billing/odoo/checkout
    (PR #21, feat/odoo-billing-integration, not merged as of 2026-09-19).

    Called over JSON-2 RPC as POST /json/2/kartatap.checkout/
    create_or_get_kartatap_checkout, authenticated with the KartaTap
    Integration (bot) user's API key. Only the identifiers, plan code and
    quantity are trusted from the caller; amount/currency/price are always
    derived from Odoo's own KartaTap SOLO/TEAM/BUSINESS products, never
    accepted as input.
    """

    _name = "kartatap.checkout"
    _description = "KartaTap Odoo-hosted checkout bridge"

    def create_or_get_kartatap_checkout(
        self,
        kartatap_company_id,
        kartatap_request_id,
        plan_code,
        quantity,
        currency,
        company_name,
        admin_email=None,
        return_url=None,
        cancel_url=None,
    ):
        self = self.sudo().with_company(_KARTATAP_COMPANY_ID)

        if plan_code not in _PLAN_MIN_QUANTITY:
            raise UserError(f"kartatap_unknown_plan:{plan_code}")
        if not isinstance(quantity, int) or quantity < _PLAN_MIN_QUANTITY[plan_code]:
            raise UserError("kartatap_invalid_quantity")
        if currency != "AED":
            raise UserError(f"kartatap_unsupported_currency:{currency}")
        if not kartatap_request_id or not kartatap_company_id:
            raise UserError("kartatap_missing_identifier")

        Sale = self.env["sale.order"].sudo()
        existing = Sale.search([("kartatap_request_id", "=", kartatap_request_id)], limit=1)
        if existing:
            return self._checkout_response(existing, plan_code, quantity, deduplicated=True)

        product = (
            self.env["product.template"]
            .sudo()
            .search(
                [
                    ("name", "=", f"KartaTap {plan_code}"),
                    ("company_id", "=", _KARTATAP_COMPANY_ID),
                ],
                limit=1,
            )
        )
        if not product:
            raise UserError(f"kartatap_product_not_found:{plan_code}")

        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("kartatap_company_id", "=", kartatap_company_id)], limit=1)
        if not partner:
            partner = Partner.create(
                {
                    "name": company_name or kartatap_company_id,
                    "email": admin_email or False,
                    "company_id": _KARTATAP_COMPANY_ID,
                    "kartatap_company_id": kartatap_company_id,
                    "customer_rank": 1,
                }
            )

        order = Sale.create(
            {
                "partner_id": partner.id,
                "company_id": _KARTATAP_COMPANY_ID,
                "kartatap_request_id": kartatap_request_id,
                "kartatap_company_id": kartatap_company_id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.product_variant_id.id,
                            "product_uom_qty": quantity,
                        },
                    )
                ],
            }
        )
        order.action_confirm()

        return self._checkout_response(order, plan_code, quantity, deduplicated=False)

    def _checkout_response(self, order, plan_code, quantity, deduplicated):
        # payment.link.wizard._compute_link() calls order.get_base_url(), which
        # (odoo/addons/website/models/ir_model.py) prefers company_id.website_id
        # .domain over web.base.url when it's set. KartaTap company (id 10) has
        # a Website record whose domain is https://app.kartatap.com -- an
        # unrelated marketing domain, not this Odoo instance's approved host.
        # KartaTap's own client (assertSafeCheckoutUrl) only accepts
        # ODOO_ALLOWED_HOSTS (default app.sgctech.ai), so a link on that other
        # domain would be rejected as odoo_invalid_response. Build the URL
        # directly against the frozen web.base.url instead of going through
        # the wizard's host resolution.
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        portal_path = order.get_portal_url(query_string=f"&payment_amount={order.amount_total}")
        checkout_url = f"{base_url}{portal_path}"
        return {
            "ok": True,
            "deduplicated": deduplicated,
            "checkout_url": checkout_url,
            "amount": order.amount_total,
            "currency": order.currency_id.name,
            "plan_code": plan_code,
            "quantity": quantity,
            "odoo": {
                "partner_id": order.partner_id.id,
                "partner_kartatap_company_id": order.kartatap_company_id,
                "sale_order_id": order.id,
                "sale_order_name": order.name,
                "sale_order_state": order.state,
                "subscription_period": "monthly",
            },
        }
