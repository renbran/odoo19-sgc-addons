"""Mirrored Stripe invoices (revenue reconciliation).

Trial subscriptions are billed by Stripe, not by Odoo: the order never goes through the
payment step, so sttl_sale_subscription never invoices it and the recurring revenue
would never reach the books. Each paid Stripe invoice is mirrored as one Odoo customer
invoice; this model is the idempotency key - one row per Stripe invoice id, so a
redelivered webhook can never book the same charge twice.
"""

from odoo import fields, models


class StripeInvoice(models.Model):
    _name = "sgc.stripe.invoice"
    _description = "Mirrored Stripe invoice (revenue reconciliation)"
    _order = "id desc"
    _rec_name = "stripe_invoice_id"

    stripe_invoice_id = fields.Char(required=True, index=True, readonly=True, copy=False)
    order_id = fields.Many2one(
        "sale.order", required=True, ondelete="cascade", index=True, readonly=True, copy=False,
    )
    move_id = fields.Many2one("account.move", readonly=True, copy=False)
    amount_paid = fields.Monetary(readonly=True, copy=False)
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, readonly=True, copy=False,
    )
    paid_at = fields.Datetime(readonly=True, copy=False)
    billing_reason = fields.Char(readonly=True, copy=False)
    event_id = fields.Char(readonly=True, index=True, copy=False)

    _stripe_invoice_id_uniq = models.Constraint(
        "unique(stripe_invoice_id)",
        "This Stripe invoice has already been mirrored.",
    )
