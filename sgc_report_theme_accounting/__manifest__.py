{
    "name": "SGC Report Theme - Accounting Documents Bridge",
    "version": "19.0.1.1.0",
    "category": "Reporting",
    "summary": "Re-points the stock Invoice/Credit Note report onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Accounting Documents Bridge
=================================================

Bridge module, same pattern as sgc_report_theme_business /
sgc_report_theme_statement / sgc_report_theme_sales: re-points
account.report_invoice_document (the Invoice / Credit Note PDF) from
web.external_layout onto sgc_report_theme_core's external_layout_sgc,
via one inherit_id t-call re-point. No value expression (t-field/t-esc)
is touched.

The bridge is created by the module's post-init hook rather than from XML
because it has to yield to account_edi_ubl_cii (core Odoo 19, UAE
e-invoicing), which rewrites the very same layout call with a literal
XPath. When both are present the two rewrites collide and the whole
registry load fails, taking the database down. The bridge therefore
exists only while account_edi_ubl_cii is not installed; a daily cron
keeps it in step if that module is installed or removed later.

Uninstalling this module reverts the report to its stock layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "account"],
    "data": [
        "data/sgc_report_theme_bridge_cron.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
