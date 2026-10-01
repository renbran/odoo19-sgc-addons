"""Stripe webhook receiver for trial subscriptions.

Stripe sends ``invoice.payment_succeeded`` / ``invoice.payment_failed`` events when the
day-14 auto-charge fires (or fails) and for every later billing cycle. Each event is
verified against the signing secret and processed idempotently via ``sgc.stripe.event``.
The day-14 charge moves the order from ``trial`` to ``active`` (a failed charge or a
cancellation locks it); every paid invoice - day 14 or recurring - is mirrored as a
posted, paid customer invoice for revenue reconciliation (``sgc.stripe.invoice``).

The endpoint is registered at ``/stripe/webhook``. The signing secret it verifies
against (``sgc_layer3_bridge.stripe_webhook_secret``) is set by hand on production.
The API key is not used here: the trial's customer, SetupIntent and subscription are
created by ``layer3.checkout`` at signup, before any event arrives.
"""

import logging
from datetime import datetime, timezone

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

    def _find_stripe_order(self, event, env):
        """The trial order a Stripe invoice belongs to, in any account state.

        Unlike ``_find_trial_order`` (restricted to ``l3_state='trial'`` for the state
        transitions), this also matches orders already ``active`` or ``locked``, because
        the recurring invoices of a live subscription arrive after the order has left
        the trial state. Only trial orders carry the Stripe ids, so the lookup cannot
        match a non-trial (Odoo-billed) order.
        """
        obj = event.get("data", {}).get("object", {}) or {}
        for value, field in (
            (obj.get("subscription") or "", "l3_stripe_subscription_id"),
            (obj.get("customer") or "", "l3_stripe_customer_id"),
        ):
            if value:
                order = env["sale.order"].sudo().search([(field, "=", value)], limit=1)
                if order:
                    return order
        request_id = (obj.get("metadata") or {}).get("l3_request_id") or ""
        if request_id:
            return env["sale.order"].sudo().search([("l3_request_id", "=", request_id)], limit=1)
        return None

    def _handle_subscription_created(self, event, env):
        """Card on file: link the Stripe ids to the order. The state stays ``trial``.

        The workspace is live for the 14 free days; only the day-14 invoice moves the
        order (``invoice.payment_succeeded`` -> active, ``invoice.payment_failed`` ->
        locked, per the no-grace trial policy). ``layer3.checkout.complete_trial`` has
        normally written both ids already, so this handler is the cross-check for a
        webhook that lands before the HTTP response does.
        """
        order = self._find_trial_order(event, env)
        if not order:
            return
        obj = event.get("data", {}).get("object", {}) or {}
        vals = {}
        if obj.get("id"):
            vals["l3_stripe_subscription_id"] = obj["id"]
        if obj.get("customer"):
            vals["l3_stripe_customer_id"] = obj["customer"]
        if vals:
            order.write(vals)

    def _handle_payment_succeeded(self, event, env):
        """A Stripe invoice was paid: activate a still-trial order, then mirror revenue.

        Stripe also emits this event for the invoice it creates when the subscription
        is created: with ``trial_period_days`` that invoice is **0 AED** (its line reads
        "Free trial for 1 x ...", ``billing_reason=subscription_create``) and it is paid
        the moment the subscription starts, so it arrives seconds after signup. Acting on
        it would flip the order to ``active`` on day 0 and skip the 14-day trial, so
        zero-amount invoices are logged and ignored (verified against a real test-mode
        delivery on 2026-09-30: evt invoice.payment_succeeded with amount_paid=0 two
        seconds after ``sub_...`` was created).

        For a real charge (``amount_paid > 0``) two things happen:
        - if the order is still in ``trial`` this is the day-14 charge: flip it to
          ``active`` and hand over the tenant;
        - in either case (day 14 or a later recurring cycle) the invoice is mirrored as
          a posted, paid customer invoice - the order never went through Odoo's payment
          step, so this is how the recurring revenue reaches the books.
        """
        order = self._find_stripe_order(event, env)
        if not order:
            return
        obj = event.get("data", {}).get("object", {}) or {}
        amount_paid = obj.get("amount_paid") or 0
        if amount_paid <= 0:
            _logger.info(
                "Stripe webhook: ignoring zero-amount invoice %s (billing_reason=%s)",
                obj.get("id") or "?",
                obj.get("billing_reason") or "?",
            )
            return
        if order.l3_state == "trial":
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
                try:
                    # sudo: the webhook runs as the public user, which cannot read
                    # mail.template records (AccessError caught below would then silently
                    # drop every day-14 email).
                    template.sudo().send_mail(order.id)
                except Exception:
                    # The charge is recorded either way; an undeliverable email must not make
                    # Stripe retry the whole event (the controller answers 500).
                    _logger.exception("Layer 3: could not email the trial-charged note for %s", order.name)
        paid_at = None
        if obj.get("paid_at"):
            try:
                # Odoo Datetime fields store naive UTC; drop the tzinfo after converting.
                paid_at = datetime.fromtimestamp(obj["paid_at"], tz=timezone.utc).replace(tzinfo=None)
            except (TypeError, ValueError, OSError):
                paid_at = None
        order._l3_mirror_stripe_invoice(
            stripe_invoice_id=obj.get("id") or event.get("id") or "",
            paid_at=paid_at,
            amount_paid=amount_paid,
            billing_reason=obj.get("billing_reason") or "",
            event_id=event.get("id") or "",
        )

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
            try:
                # sudo: public-user webhook env cannot read mail.template (see above).
                template.sudo().send_mail(order.id)
            except Exception:
                _logger.exception("Layer 3: could not email the trial lockout for %s", order.name)

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
