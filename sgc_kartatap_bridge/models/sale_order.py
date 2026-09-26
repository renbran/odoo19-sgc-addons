import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Links an Odoo quotation/subscription to the KartaTap request that created it.

    `kartatap_request_id` is the idempotency key supplied by KartaTap: a replayed
    request must return the SAME quotation instead of creating a second one. It is
    nullable (every existing order stays valid) and unique when set, so the database -
    not application logic - is the last line of defence against duplicates.
    """

    _inherit = "sale.order"

    kartatap_request_id = fields.Char(
        string="KartaTap Request ID",
        index=True,
        copy=False,
        help="Idempotency key of the KartaTap checkout request that created this order.",
    )
    kartatap_company_id = fields.Char(
        string="KartaTap Company ID",
        index=True,
        copy=False,
        help="KartaTap tenant identifier this order was created for.",
    )

    # Odoo 19: declared with models.Constraint; `_sql_constraints` is ignored, which would
    # have left idempotency protected only by application logic instead of by the database.
    _kartatap_request_id_uniq = models.Constraint(
        "unique(kartatap_request_id)",
        "An order already exists for this KartaTap request ID.",
    )


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_price_unit(self):
        """KartaTap orders are priced from kartatap.price in the order's own currency.

        `sttl_sale_subscription` resets price_unit on every recompute (including the
        quantity bump of each recurring invoice) to its single currency-less number,
        which would charge a USD subscription the AED figure at renewal. This runs after
        it (this module depends on it) and restores the correct price for KartaTap
        orders only; every other order keeps the add-on's behaviour.
        """
        super()._compute_price_unit()
        Price = self.env["kartatap.price"].sudo()
        for line in self:
            order = line.order_id
            if not order.kartatap_request_id or not order.recurrance_id or not line.product_id:
                continue
            plan = Price._plan_for_product(line.product_id)
            if not plan:
                continue
            price = Price._find(plan, order.recurrance_id.unit, order.currency_id)
            if price:
                line.price_unit = price.amount
