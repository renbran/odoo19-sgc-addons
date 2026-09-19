import logging

from odoo import models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    """Once a KartaTap checkout order's payment reaches state=done, send the
    subscription.activated entitlement event exactly once
    (kartatap_event_sent guards against _post_process running more than
    once for the same transaction, e.g. on both the redirect confirmation
    and the Stripe webhook).
    """

    _inherit = "payment.transaction"

    def _post_process(self):
        super()._post_process()
        for tx in self:
            if tx.state != "done":
                continue
            orders = tx.sale_order_ids.filtered(
                lambda o: o.kartatap_request_id and not o.kartatap_event_sent
            )
            for order in orders:
                _logger.info(
                    "sgc_kartatap_bridge: payment done for KartaTap order %s "
                    "(transaction %s), sending entitlement event",
                    order.name,
                    tx.reference,
                )
                order._send_kartatap_entitlement_event("subscription.activated", "active")
