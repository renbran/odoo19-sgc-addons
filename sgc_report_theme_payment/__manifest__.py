{
    "name": "SGC Report Theme - Payment Receipt Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-points the stock Payment Receipt report onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Payment Receipt Bridge
============================================

Bridge module: re-points account.report_payment_receipt_document (the
sub-template account.report_payment_receipt calls per payment) from
web.external_layout onto sgc_report_theme_core's external_layout_sgc.

Uninstalling this module reverts the report to its stock layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "account"],
    "data": [
        "views/payment_reports_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
