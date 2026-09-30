"""Thin Stripe SDK wrapper for the 14-day trial (Option A in the trial plan).

The bridge talks to Stripe directly so it does not depend on Odoo's payment_provider table
for trial signups. The card is captured on the frontend via Stripe Elements; the bridge
calls Stripe only to:

* ``create_trial_customer_and_subscription`` — at trial signup, after Odoo creates the
  draft order. Creates a Stripe customer and a subscription with ``trial_period_days=14``.
  Stripe handles the day-14 auto-charge natively; the bridge reacts to the resulting
  webhook (``invoice.payment_succeeded`` / ``invoice.payment_failed``).
* ``verify_webhook`` — verifies the ``Stripe-Signature`` header on incoming webhooks from
  Stripe so the Odoo controller can trust the event payload.

The module is pure Python (no Odoo import) so it is unit-testable without Odoo or Stripe.
Tests patch ``stripe.Customer.create`` / ``stripe.Subscription.create`` / ``stripe.Webhook``.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# Trial period in days, per the founder decision 2026-09-30.
TRIAL_PERIOD_DAYS = 14


def create_trial_customer_and_subscription(api_key, email, name, price_id, cycle, metadata=None):
    """Create a Stripe customer and a subscription with ``trial_period_days=14``.

    Returns ``(customer_id, subscription_id)``. Raises ``stripe.error.StripeError`` on any
    Stripe API error. The caller (the bridge controller) owns retry policy.
    """
    import stripe
    stripe.api_key = api_key
    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata=metadata or {},
    )
    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": price_id}],
        trial_period_days=TRIAL_PERIOD_DAYS,
        metadata=metadata or {},
    )
    return customer.id, subscription.id


def verify_webhook(payload, signature_header, webhook_secret):
    """Verify a Stripe webhook signature and return the parsed event dict.

    ``payload`` is the raw request body (bytes). ``signature_header`` is the value of the
    ``Stripe-Signature`` request header. ``webhook_secret`` is the endpoint signing secret
    from the Stripe dashboard. Raises ``stripe.error.SignatureVerificationError`` on a bad
    signature; the caller returns HTTP 400.
    """
    import stripe
    event = stripe.Webhook.construct_event(payload, signature_header, webhook_secret)
    return event
