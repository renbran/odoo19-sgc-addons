# -*- coding: utf-8 -*-
"""Paid-deal metric provider.

A deal is NEVER counted as "paid" merely because its opportunity reached the
Won stage.  Payment is always evidenced by accounting state:

    account.move (move_type in out_invoice/out_refund, state = posted,
                  payment_state in the configured qualifying set)
        -> account.move.line
        -> sale_order_line_invoice_rel   (the real M2M link; there is no
                                          scalar FK from move line to sale
                                          order line in this database)
        -> sale.order.line -> sale.order

``qualifying_payment_mode``:

* ``paid``          - payment_state == 'paid' only (DEFAULT)
* ``paid_partial``  - 'paid' or 'partial'
* ``paid_inclusive``- 'paid', 'partial' or 'in_payment'

Odoo's full ``payment_state`` enum is handled defensively even though only
``paid`` / ``not_paid`` / ``blocked`` appear in the current data set.

ACCOUNTING NON-DISCLOSURE
-------------------------
This provider only ever returns *aggregates* (a count and a monetary sum).
It never returns invoice ids, move names, partner ids, journal information or
any drill-down domain on an accounting model.  The drill-down domain returned
points at ``sale.order`` records the CES user already owns, so a CES user can
never reach an accounting record through this metric.
"""
from odoo import api, models

PAYMENT_MODES = {
    "paid": ("paid",),
    "paid_partial": ("paid", "partial"),
    "paid_inclusive": ("paid", "partial", "in_payment"),
}
ALL_PAYMENT_STATES = (
    "not_paid",
    "in_payment",
    "paid",
    "partial",
    "reversed",
    "blocked",
    "invoicing_legacy",
)


class SgcCesMetricPayment(models.AbstractModel):
    _name = "sgc.ces.metric.payment"
    _description = "SGC CES Paid Deal Metric Provider"

    @api.model
    def _qualifying_states(self, params):
        mode = (params or {}).get("qualifying_payment_mode") or "paid"
        states = PAYMENT_MODES.get(mode, PAYMENT_MODES["paid"])
        return [s for s in states if s in ALL_PAYMENT_STATES]

    @api.model
    def _paid_orders(self, ctx):
        """Return the ``sale.order`` recordset with qualifying payments.

        Runs entirely through the ORM; the M2M hop uses the ``invoice_lines``
        relation on ``sale.order.line`` which is backed by
        ``sale_order_line_invoice_rel``.
        """
        params = ctx.get("params") or {}
        states = self._qualifying_states(params)
        move_domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("payment_state", "in", states),
        ]
        if ctx.get("date_from"):
            move_domain.append(("invoice_date", ">=", ctx["date_from"]))
        if ctx.get("date_to"):
            move_domain.append(("invoice_date", "<=", ctx["date_to"]))
        if ctx.get("company_ids"):
            move_domain.append(("company_id", "in", list(ctx["company_ids"])))
        moves = self.env["account.move"].sudo().search(move_domain)
        if not moves:
            return self.env["sale.order"].sudo().browse(), states
        move_lines = moves.mapped("line_ids")
        if not move_lines:
            return self.env["sale.order"].sudo().browse(), states
        order_lines = self.env["sale.order.line"].sudo().search(
            [("invoice_lines", "in", move_lines.ids)]
        )
        orders = order_lines.mapped("order_id")
        order_domain = [("id", "in", orders.ids), ("user_id", "=", ctx["user_id"])]
        if params.get("require_opportunity"):
            order_domain.append(("opportunity_id", "!=", False))
        return self.env["sale.order"].sudo().search(order_domain), states

    @api.model
    def _metric_paid_deal_count(self, ctx):
        orders, states = self._paid_orders(ctx)
        return {
            "value": float(len(orders)),
            # Safe drill-down: sale orders owned by the user, never invoices.
            "domain": [("id", "in", orders.ids)] if orders else [("id", "=", 0)],
            "res_model": "sale.order",
            "detail": {"qualifying_payment_states": states},
        }

    @api.model
    def _metric_paid_deal_value(self, ctx):
        orders, states = self._paid_orders(ctx)
        value = sum(orders.mapped("amount_untaxed")) if orders else 0.0
        return {
            "value": float(value),
            "domain": [("id", "in", orders.ids)] if orders else [("id", "=", 0)],
            "res_model": "sale.order",
            "detail": {"qualifying_payment_states": states},
        }
