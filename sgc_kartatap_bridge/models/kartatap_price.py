from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..lib.entitlement_contract import PLANS

INTERVALS = [("month", "Monthly"), ("year", "Yearly")]


class KartatapPrice(models.Model):
    """The KartaTap price book, per currency, as Odoo bills it.

    One row per (plan, billing interval, currency) holding the per-seat amount in that
    currency. It mirrors KartaTap's published price book (src/lib/pricing.ts) and is
    the ONLY price source for KartaTap orders: `sttl_sale_subscription` keeps a single
    currency-less number per product and period, which would reprice a USD order at the
    AED figure. A currency is billable when it is active in Odoo and has rows here, so
    opening a new market is configuration, not code.
    """

    _name = "kartatap.price"
    _description = "KartaTap price book (per currency)"
    _order = "currency_id, plan_code, interval"
    _rec_name = "plan_code"

    plan_code = fields.Selection([(p, p) for p in PLANS], required=True)
    interval = fields.Selection(INTERVALS, required=True)
    currency_id = fields.Many2one("res.currency", required=True, ondelete="restrict")
    amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
        help="Price per seat for one billing interval, in this row's currency.",
    )
    active = fields.Boolean(default=True)

    _unique_price = models.Constraint(
        "unique(plan_code, interval, currency_id)",
        "There is already a KartaTap price for this plan, interval and currency.",
    )

    @api.constrains("amount")
    def _check_amount(self):
        for row in self:
            if row.amount <= 0:
                raise ValidationError(_("A KartaTap price must be greater than zero."))

    @api.model
    def _find(self, plan_code, interval, currency):
        return self.sudo().search(
            [
                ("plan_code", "=", plan_code),
                ("interval", "=", interval),
                ("currency_id", "=", currency.id),
            ],
            limit=1,
        )

    @api.model
    def _billable_currency(self, code):
        """The active res.currency for an ISO code, or UserError if KartaTap cannot bill it."""
        currency = self.env["res.currency"].sudo().with_context(active_test=False).search(
            [("name", "=", code)], limit=1
        )
        if not currency or not currency.active or not self.sudo().search_count(
            [("currency_id", "=", currency.id)]
        ):
            raise UserError(_("kartatap_currency_not_billable:%s") % code)
        return currency

    @api.model
    def _plan_for_product(self, product):
        from .kartatap_checkout import DEFAULT_PRODUCT_CODE, PRODUCT_CODE_PARAM

        checkout = self.env["kartatap.checkout"]
        codes = {
            checkout._param(PRODUCT_CODE_PARAM[plan], DEFAULT_PRODUCT_CODE[plan]): plan
            for plan in PLANS
        }
        return codes.get(product.default_code)
