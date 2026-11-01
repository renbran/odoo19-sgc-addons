# -*- coding: utf-8 -*-
{
    "name": "SGC Accounting Checkout",
    "version": "19.0.1.2.0",
    "category": "Accounting/Accounting",
    "summary": "Paid website signup for the SGC accounting packages; portal opens once payment settles",
    "description": """
Website signup for the five SGC accounting packages (START, ESSENTIAL, COMPLIANCE,
BUSINESS, GROWTH CFO). There is no free trial.

* sgctech.ai calls sgc.accounting.checkout.create_checkout over JSON-2 and sends the
  visitor to the Sign & Pay page of the quotation it returns.
* The accounting client record and the portal invitation are created only when the
  order is confirmed AND paid (a done payment transaction or a paid invoice).
* A cron retries activation, so an invoice paid by bank transfer also opens the portal.
* Renewals: a daily cron invoices each new period (monthly, or annual 12-for-11) when the
  paid period ends, posts it and emails it with the pay link. Untick "Accounting renewals"
  on the order (or suspend/archive the client) to stop.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sale", "payment", "sgc_accounting_clients"],
    "data": [
        "security/checkout_security.xml",
        "security/ir.model.access.csv",
        "data/checkout_data.xml",
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
