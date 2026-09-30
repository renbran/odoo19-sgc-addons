{
    "name": "SGC Layer 3 Bridge",
    "summary": "Layer 3 subscription signup, Order Form checkout, account states and tenant sync.",
    "description": """
Odoo side of the SGC Layer 3 (Rent - Subscription Layer) signup and billing flow.

* ``layer3.checkout.create_or_get_checkout`` - called by the sgctech.ai signup page over
  JSON-2. Creates (idempotently) the customer and the Order Form quotation with its
  recurring plan and returns the hosted Sign & Pay link.
* Account states per MSA SGC-MSA-2026-02 section 6: Active, Grace (days 1-7 overdue),
  Read-only (days 8-29), Archive (day 30, or 30 days after a cancellation takes effect),
  Deletion (after the archive period).
* 14-day trial signup with card-required auto-renew; day-14 decline immediately locks the
  workspace (no grace period for trial signups).
* Trade-licence check that never blocks onboarding: pending / submitted / rejected /
  approved / expiring, visible to SGC on the order and to the client in its tenant.
* A durable, HMAC-signed outbox that tells the tenant receiver on vps-root what each
  tenant should look like (``tenant.sync`` snapshots).
""",
    "version": "19.0.1.3.0",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "category": "Sales/Sales",
    "depends": [
        "sale_management",
        "account",
        "payment",
        "portal",
        "sttl_sale_subscription",
    ],
    "data": [
        "security/layer3_security.xml",
        "security/ir.model.access.csv",
        "data/layer3_config.xml",
        "data/layer3_products.xml",
        "data/layer3_cron.xml",
        "data/layer3_email_templates.xml",
        "views/sale_order_views.xml",
        "views/layer3_event_views.xml",
        "views/portal_templates.xml",
    ],
    "external_dependencies": {"python": ["requests", "stripe"]},
    "installable": True,
    "auto_install": False,
    "application": False,
}
