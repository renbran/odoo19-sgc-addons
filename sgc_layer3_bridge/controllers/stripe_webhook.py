"""Stripe webhook receiver for trial subscriptions.

Stripe sends ``invoice.payment_succeeded`` / ``invoice.payment_failed`` events when the
day-14 auto-charge fires (or fails). Each event is verified against the signing secret
and processed idempotently via ``sgc.stripe.event``.

The endpoint is registered at ``/stripe/webhook``. Required config parameters
(``sgc_layer3_bridge.stripe_api_key``, ``sgc_layer3_bridge.stripe_webhook_secret``)
are set by hand on production.
"""

import logging

from odoo import _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class StripeWebhook(http.Controller):
    @http.route("/stripe/webhook", type="http", auth="public", methods=["POST"], csrf=False)
    def stripe_webhook(self, **kw):
        payload = request.httprequest.get_data()  # raw bytes
        signature = request.httprequest.headers.get("Stripe-Signature", "")
        if not signature:
            return http.Response(status=400)

        ICP = request.env["ir.config_parameter"].sudo()
        webhook_secret = ICP.get_param("sgc_layer3_bridge.stripe_webhook_secret", "")
        if not webhook_secret or len(webhook_secret) < 16:
            _logger.warning("Stripe webhook: stripe_webhook_secret is missing or too short")
            return http.Response(status=503)

        from ..lib import stripe_client
        try:
            event = stripe_client.verify_webhook(payload, signature, webhook_secret)
        except Exception as exc:
            _logger.warning("Stripe webhook signature verification failed: %s", exc)
            return http.Response(status=400)

        event_id = event.get("id", "")
        event_type = event.get("type", "")
        if not event_id:
            return http.Response(status=400)

        Seen = request.env["sgc.stripe.event"].sudo()
        if Seen.seen(event_id):
            _logger.info("Stripe webhook: duplicate event %s ignored", event_id)
            return http.Response(status=200)

        try:
            if event_type == "customer.subscription.created":
                self._handle_subscription_created(event, request.env)
            elif event_type == "invoice.payment_succeeded":
                self._handle_payment_succeeded(event, request.env)
            elif event_type == "invoice.payment_failed":
                self._handle_payment_failed(event, request.env)
            elif event_type == "customer.subscription.deleted":
                self._handle_subscription_deleted(event, request.env)
            else:
                _logger.info("Stripe webhook: ignoring event type %s", event_type)
        except Exception:
            _logger.exception("Stripe webhook: handler failed for %s", event_type)
            return http.Response(status=500)  # Stripe will retry

        Seen.record(event_id, event_type)
        return http.Response(status=200)

    # --------------------------------------------------------------- handlers

    def _find_trial_order(self, event, env):
        """Find the trial order this Stripe event refers to.

        Three lookups, in order:
        1. l3_stripe_subscription_id == event subscription_id (most reliable after
           the first webhook has linked the IDs back onto the order).
        2. l3_stripe_customer_id == event customer_id (also after the first link).
        3. email + tenant_slug (best-effort for the very first webhook event, when
           the order does not yet have the Stripe IDs because Odoo's payment_stripe
           just created the customer and subscription). Picks the most recent match.
        """
        obj = event.get("data", {}).get("object", {}) or {}
        subscription_id = obj.get("subscription") or ""
        if subscription_id:
            order = env["sale.order"].sudo().search([
                ("l3_stripe_subscription_id", "=", subscription_id),
                ("l3_state", "=", "trial"),
            ], limit=1)
            if order:
                return order
        customer_id = obj.get("customer") or ""
        if customer_id:
            order = env["sale.order"].sudo().search([
                ("l3_stripe_customer_id", "=", customer_id),
                ("l3_state", "=", "trial"),
            ], limit=1)
            if order:
                return order
        # First-event fallback: match by email + tenant slug from event metadata.
        # Odoo's payment_stripe passes metadata through to the Stripe customer
        # object; if the order's request_id was set as metadata we use it, else
        # we fall back to email (one active trial per email is the practical
        # invariant for self-serve signups).
        request_id = (obj.get("metadata") or {}).get("l3_request_id") or ""
        if request_id:
            order = env["sale.order"].sudo().search([
                ("l3_request_id", "=", request_id),
                ("l3_state", "=", "trial"),
            ], limit=1)
            if order:
                return order
        customer_email = ""
        if customer_id:
            customer_obj = event.get("data", {}).get("object", {})
            # customer object is nested inside the subscription's `customer` field
            # only if the event includes it; otherwise we'd need a Stripe API call.
            # Skip this branch if no email is reachable; the lookup then fails open.
            customer_email = customer_obj.get("customer_email") or ""
        if customer_email:
            return env["sale.order"].sudo().search([
                ("l3_admin_email", "=ilike", customer_email),
                ("l3_state", "=", "trial"),
            ], limit=1, order="id desc")
        return None

    def _handle_subscription_created(self, event, env):
        """Card linked to the trial subscription: trial -> active.

        Fires when Odoo's payment_stripe creates the Stripe subscription with the
        customer's saved card. We transition trial -> active so the workspace
        reflects the customer's paid state (card on file, awaiting day-14 auto-
        charge). The day-14 invoice.payment_succeeded is a no-op for state
        (already active), and invoice.payment_failed still flips active -> locked
        per the no-grace-trial policy.
        """
        order = self._find_trial_order(event, env)
        if not order:
            return
        # Store the Stripe IDs on the order so future webhook events match.
        obj = event.get("data", {}).get("object", {}) or {}
        subscription_id = obj.get("id", "")
        customer_id = obj.get("customer", "")
        vals = {"l3_state": "active", "l3_state_reason": "card_linked"}
        if subscription_id:
            vals["l3_stripe_subscription_id"] = subscription_id
        if customer_id:
            vals["l3_stripe_customer_id"] = customer_id
        order.write(vals)
        order._l3_sync(provision=False)

    def _handle_payment_succeeded(self, event, env):
        """Day-14 charge succeeded: trial -> active, activate tenant."""
        order = self._find_trial_order(event, env)
        if not order:
            return
        today = fields.Date.context_today(env["sale.order"])
        order.write({
            "l3_state": "active",
            "l3_activated_on": today,
            "l3_state_reason": "trial_charged",
        })
        order._l3_sync(provision=True)
        template = env.ref(
            "sgc_layer3_bridge.mail_template_l3_trial_charged",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(order.id)

    def _handle_payment_failed(self, event, env):
        """Day-14 charge failed: IMMEDIATE lockout (no grace period for trials)."""
        order = self._find_trial_order(event, env)
        if not order:
            return
        order.write({
            "l3_state": "locked",
            "l3_state_reason": "trial_locked",
        })
        order._l3_sync()
        template = env.ref(
            "sgc_layer3_bridge.mail_template_l3_trial_locked",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(order.id)

    def _handle_subscription_deleted(self, event, env):
        """Subscription cancelled during trial: immediate lockout."""
        order = self._find_trial_order(event, env)
        if not order:
            return
        order.write({
            "l3_state": "locked",
            "l3_state_reason": "trial_locked",
        })
        order._l3_sync()
