from odoo import models
from odoo.exceptions import ValidationError

CHARGEABLE_STATES = ("pending", "authorized", "done")


class PaymentTransaction(models.Model):
    """One chargeable payment per Layer 3 Order Form.

    A client with the Sign & Pay page open in two tabs must never be charged twice. Every
    provider (Stripe included) reaches a chargeable state through _set_pending,
    _set_authorized or _set_done, so the guard sits there, under a row lock on the order.
    Orders that are not Layer 3 are untouched.
    """

    _inherit = "payment.transaction"

    def _set_pending(self, state_message=None, **kwargs):
        self._l3_guard("pending")
        return super()._set_pending(state_message=state_message, **kwargs)

    def _set_authorized(self, state_message=None, **kwargs):
        self._l3_guard("authorized")
        return super()._set_authorized(state_message=state_message, **kwargs)

    def _set_done(self, state_message=None, **kwargs):
        self._l3_guard("done")
        return super()._set_done(state_message=state_message, **kwargs)

    def _l3_guard(self, target_state):
        for tx in self:
            orders = tx.sale_order_ids.filtered(lambda o: o.l3_request_id)
            if len(orders) != 1:
                continue
            self.env.cr.execute("SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (orders.id,))
            other = self.sudo().search(
                [
                    ("sale_order_ids", "in", orders.ids),
                    ("state", "in", CHARGEABLE_STATES),
                    ("id", "!=", tx.id),
                ],
                limit=1,
            )
            if other:
                raise ValidationError(
                    "Order %s already has a chargeable payment (%s, %s); transaction %s cannot become %s."
                    % (orders.name, other.reference, other.state, tx.reference, target_state)
                )
