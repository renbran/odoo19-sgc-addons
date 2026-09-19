{
    "name": "SGC KartaTap Bridge",
    "version": "19.0.1.0.0",
    "category": "Sales/Subscriptions",
    "summary": "Odoo-hosted checkout + signed entitlement events for the KartaTap billing integration.",
    "description": """
SGC KartaTap Bridge
====================

Implements the Odoo-side half of the KartaTap <-> Odoo 19 billing integration
described in kartatap/docs/ODOO_BILLING_INTEGRATION.md (PR #21, not merged as
of 2026-09-19):

- `kartatap.checkout.create_or_get_kartatap_checkout` -- the JSON-2 RPC method
  KartaTap's POST /api/billing/odoo/checkout calls to create (or, for a
  repeated kartatap_request_id, look up) a sale order for a KartaTap tenant
  and return an Odoo-hosted Stripe payment link. Idempotent on
  kartatap_request_id.
- A `payment.transaction._post_process()` override that, once a KartaTap
  order's payment reaches state=done, POSTs a signed
  `subscription.activated` entitlement event to KartaTap
  (ir.config_parameter `kartatap.entitlement_url` /
  `kartatap.entitlement_signing_secret`), matching the HMAC-SHA256
  `v1=<hex>` contract KartaTap's entitlements.ts verifies. Sent at most once
  per order (kartatap_event_sent guard).

Scope is deliberately minimal: this proves the SOLO/qty1 pilot path
end-to-end (single event type: subscription.activated). Renewal, dunning,
cancellation and refund events are not implemented here.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sale", "payment"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
