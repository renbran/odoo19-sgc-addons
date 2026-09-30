"""Thin Stripe SDK wrapper for the 14-day card-required trial.

The bridge talks to Stripe directly so it does not depend on Odoo's payment_provider
machinery for trial signups. The card is collected by Stripe Elements on our own
``/subscribe`` page, and the bridge calls Stripe only to:

* ``create_customer`` — once per trial signup, the Stripe customer the card attaches to.
* ``create_setup_intent`` — the Elements Payment Element confirms it (no charge, card
  saved for off-session use).
* ``retrieve_setup_intent`` — server-side check, after Elements confirms, so a client
  cannot claim a card it never collected.
* ``ensure_trial_price`` — idempotent recurring Price (lookup key) for the order total.
* ``create_trial_subscription`` — the subscription with ``trial_period_days=14``.
  Stripe handles the day-14 auto-charge natively; the bridge reacts to the resulting
  webhook (``invoice.payment_succeeded`` / ``invoice.payment_failed``).
* ``verify_webhook`` — verifies the ``Stripe-Signature`` header on incoming webhooks from
  Stripe so the Odoo controller can trust the event payload.

The module is pure Python (no Odoo import) so it is unit-testable without Odoo or Stripe.
Every function returns plain dicts; tests patch these functions themselves.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# Trial period in days, per the founder decision 2026-09-30.
TRIAL_PERIOD_DAYS = 14


def create_customer(api_key, email, name, metadata=None):
    """Create the Stripe customer the trial card attaches to. Returns the customer id."""
    import stripe
    stripe.api_key = api_key
    customer = stripe.Customer.create(
        email=email,
        name=name,
        metadata=metadata or {},
    )
    return customer.id


def create_setup_intent(api_key, customer_id):
    """SetupIntent for the card-only Payment Element: saves the card, charges nothing.

    Returns ``{"id": ..., "client_secret": ...}``. ``usage="off_session"`` is what lets
    Stripe charge the saved card on day 14 without asking the customer again.
    """
    import stripe
    stripe.api_key = api_key
    intent = stripe.SetupIntent.create(
        customer=customer_id,
        usage="off_session",
        payment_method_types=["card"],
        metadata={"purpose": "l3_trial_card"},
    )
    return {"id": intent.id, "client_secret": intent.client_secret}


def retrieve_setup_intent(api_key, setup_intent_id):
    """Server-side read of a SetupIntent. Returns ``{"id", "status", "payment_method",
    "customer"}`` — the caller only proceeds on ``status == "succeeded"``."""
    import stripe
    stripe.api_key = api_key
    intent = stripe.SetupIntent.retrieve(setup_intent_id)
    return {
        "id": intent.id,
        "status": intent.status,
        "payment_method": intent.payment_method or "",
        "customer": intent.customer or "",
    }


def ensure_trial_price(api_key, amount_minor, currency, interval="month", lookup_key=None):
    """Return the Price id for the recurring trial plan, creating it once.

    ``amount_minor`` is the smallest currency unit (AED 875.00 -> 87500). The
    ``lookup_key`` makes the call idempotent: a retry finds the Price it created before
    instead of billing the same plan twice under two different Prices.
    """
    import stripe
    stripe.api_key = api_key
    if lookup_key:
        found = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)
        if found.data:
            return found.data[0].id
    product = stripe.Product.create(
        name="SGC Layer 3 Workspace",
        metadata={"purpose": "l3_trial"},
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount_minor,
        currency=currency,
        recurring={"interval": interval},
        lookup_key=lookup_key or "",
        metadata={"purpose": "l3_trial"},
    )
    return price.id


def create_trial_subscription(api_key, customer_id, price_id, payment_method_id, metadata=None):
    """Start the subscription with the collected card and ``trial_period_days=14``.

    Returns ``{"id", "customer", "trial_end"}`` (``trial_end`` is a Unix timestamp).
    """
    import stripe
    stripe.api_key = api_key
    stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        trial_period_days=TRIAL_PERIOD_DAYS,
        default_payment_method=payment_method_id,
        payment_settings={"save_default_payment_method": "on_subscription"},
        metadata=metadata or {},
    )
    return {
        "id": subscription.id,
        "customer": subscription.customer or "",
        "trial_end": subscription.trial_end,
    }


def create_trial_customer_and_subscription(api_key, email, name, price_id, cycle, metadata=None):
    """Create a Stripe customer and a subscription with ``trial_period_days=14``.

    Returns ``(customer_id, subscription_id)``. Raises ``stripe.error.StripeError`` on any
    Stripe API error. The caller (the bridge controller) owns retry policy.
    """
    import stripe
    stripe.api_key = api_key
    customer_id = create_customer(api_key, email, name, metadata)
    subscription = stripe.Subscription.create(
        customer=customer_id,
        items=[{"price": price_id}],
        trial_period_days=TRIAL_PERIOD_DAYS,
        metadata=metadata or {},
    )
    return customer_id, subscription.id


def verify_webhook(payload, signature_header, webhook_secret):
    """Verify a Stripe webhook signature and return the parsed event dict.

    ``payload`` is the raw request body (bytes). ``signature_header`` is the value of the
    ``Stripe-Signature`` request header. ``webhook_secret`` is the endpoint signing secret
    from the Stripe dashboard. Raises ``stripe.error.SignatureVerificationError`` on a bad
    signature; the caller returns HTTP 400.

    stripe-python >= 11 returns a ``stripe.Event`` (a ``StripeObject``), which is *not* a
    dict and has no ``.get()``: calling it raises ``AttributeError: 'get' is a dict
    method, but a Event is not a dict``. The controller reads ``event.get("id")`` before
    any try/except, so an unconverted object 500s every single delivery. The event is
    therefore normalised to a plain nested dict here.
    """
    import stripe
    event = stripe.Webhook.construct_event(payload, signature_header, webhook_secret)
    if isinstance(event, dict):
        return event
    to_dict = getattr(event, "to_dict", None)
    if not callable(to_dict):
        raise TypeError(
            "stripe.Webhook.construct_event returned %s, which cannot be read as a dict"
            % type(event).__name__
        )
    return to_dict()
