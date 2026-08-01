{
    "name": "SGC Report Theme - Sales Documents Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-points the stock Quotation/Sales Order report onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Sales Documents Bridge
===========================================

Bridge module, same pattern as sgc_report_theme_business /
sgc_report_theme_statement: re-points sale.report_saleorder_document
(the Quotation / Sales Order PDF) from web.external_layout onto
sgc_report_theme_core's external_layout_sgc, via one inherit_id t-call
re-point. No value expression (t-field/t-esc) is touched.

Uninstalling this module reverts the report to its stock layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "sale_management", "sale"],
    "data": [
        "views/sales_reports_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
