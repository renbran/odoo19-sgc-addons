"""Stripe webhook event idempotency log.

Stripe delivers webhooks at-least-once. Each event has an immutable ``event_id``; we
record every event_id we have already processed so a redelivery is a no-op. The
``/stripe/webhook`` controller writes here; nothing else does.
"""

from odoo import api, fields, models


class StripeEvent(models.Model):
    _name = "sgc.stripe.event"
    _description = "Stripe webhook event idempotency log"
    _order = "id desc"
    _rec_name = "event_id"

    event_id = fields.Char(required=True, index=True, readonly=True)
    event_type = fields.Char(readonly=True)
    processed_at = fields.Datetime(required=True, default=fields.Datetime.now)

    _event_id_uniq = models.Constraint("unique(event_id)", "Stripe event ID already processed.")

    @api.model
    def seen(self, event_id):
        return bool(self.sudo().search_count([("event_id", "=", event_id)]))

    @api.model
    def record(self, event_id, event_type):
        return self.sudo().create({
            "event_id": event_id,
            "event_type": event_type or "",
        })
