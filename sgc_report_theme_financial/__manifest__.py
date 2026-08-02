{
    "name": "SGC Report Theme - Financial Reports Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-points the live accounting_pdf_reports/om_account_daily_reports "
               "financial reports onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Financial Reports Bridge
==============================================

Bridge module for the 9 financial reports actually installed and used
today (accounting_pdf_reports + om_account_daily_reports) - NOT the
separate, not-yet-installed sgc_dynamic_financial_report (XLSX) module,
which is out of scope here.

These 9 templates call web.internal_layout, not web.external_layout
like the other bridges - Odoo's stock "internal" reports (financial
statements, ledgers) intentionally use a lighter layout than customer-
facing documents. Re-pointing them to external_layout_sgc is a bigger
visual change than the other bridges' pattern (full letterhead instead
of a minimal internal header), but that's the explicit goal here: these
reports currently render with NO SGC branding at all, and Brand
Guidelines v3.0 Chapter 09 (Landscape System) names "financial reports
with wide data tables" as a first-class use case for the design system.
external_layout_sgc already defends against being called without going
through the web.external_layout dispatcher (see report_layout_sgc.xml's
2026-07-23 fix) so this works despite the different calling convention.

Templates re-pointed:
- accounting_pdf_reports.report_agedpartnerbalance (Aged Partner Balance)
- accounting_pdf_reports.report_financial (Financial Report)
- accounting_pdf_reports.report_general_ledger (General Ledger)
- accounting_pdf_reports.report_partnerledger (Partner Ledger)
- accounting_pdf_reports.report_tax (Tax Report)
- accounting_pdf_reports.report_trialbalance (Trial Balance)
- om_account_daily_reports.report_bankbook (Bank Book)
- om_account_daily_reports.report_cashbook (Cash Book)
- om_account_daily_reports.report_daybook (Day Book)

Uninstalling this module reverts all 9 to their stock internal layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "sgc_report_theme_core",
        "accounting_pdf_reports",
        "om_account_daily_reports",
    ],
    "data": [
        "views/financial_reports_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
