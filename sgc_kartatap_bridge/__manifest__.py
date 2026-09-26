{
    "name": "KartaTap Bridge",
    "summary": "Atomic Odoo-hosted KartaTap checkout (quotation + recurring plan + payment link).",
    "description": """
KartaTap Bridge exposes a single atomic business method that KartaTap calls to start a
hosted Odoo checkout for one KartaTap tenant.

Odoo remains the financial system of record: this module creates the partner (mapped by an
immutable KartaTap identifier), the quotation with its recurring plan, and the hosted
payment link. It does NOT create invoices, payments or accounting entries - those are
produced by the normal Odoo sale/payment flow once the customer actually pays.

Version 19.0.1.1.0 adds the Odoo -> KartaTap entitlement push: a durable outbox of
HMAC-signed events (activated, renewed, past_due, canceled) delivered by a cron job,
disabled until an administrator enables it and configures the shared signing secret.
Checkout accepts KartaTap's billing_interval (month/year) and display currency.
""",
    "version": "19.0.1.1.0",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "category": "Sales/Sales",
    "depends": [
        "sale_management",
        "account",
        "payment",
        "payment_stripe",
        "sttl_sale_subscription",
    ],
    "data": [
        "security/kartatap_security.xml",
        "security/ir.model.access.csv",
        "data/kartatap_config.xml",
        "data/kartatap_cron.xml",
        "views/kartatap_entitlement_views.xml",
    ],
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "auto_install": False,
    "application": False,
}
