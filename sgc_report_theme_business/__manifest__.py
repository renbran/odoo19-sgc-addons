{
    "name": "SGC Report Theme - Business Documents Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-points SGC's stock-external_layout business reports "
                "(sale agreements, AML/KYC compliance, follow-up, journal "
                "entries) onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Business Documents Bridge
===============================================

Bridge module (RALPLAN consensus plan, 2026-07-23). Re-points 9 report
templates that were still rendering through the stock
web.external_layout dispatcher onto sgc_report_theme_core's
external_layout_sgc, via one inherit_id t-call re-point per template.

Deliberately EXCLUDES reports that already have their own bespoke,
complete custom design (sgc_construction_management's own
external_layout_sgc theme, sgc_quotation_proposal's Inter/Cormorant
Garamond design system, kyc_management's report_kyc_application inline
styling) - those are already professionally themed and re-pointing them
would override existing, working custom work rather than fix a gap.

Templates re-pointed:
- sale_agreement_report.report_sale_agreement
- sale_agreement_report.report_sale_agreement_yearly
- aml_compliance.report_risk_assessment_document
- aml_compliance.report_goaml_dossier_document
- aml_compliance.report_screening_certificate
- aml_compliance.report_consolidated_kyc
- kyc_management.report_kyc_approvals_summary_template
- om_account_followup.report_followup
- accounting_pdf_reports.report_journal_entries

N3 invariant: each of the 9 templates above is targeted by exactly one
inherit_id record in this module; none is shared with any other bridge.
Uninstalling this module reverts all 9 to their stock layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "sgc_report_theme_core",
        "sale_agreement_report",
        "aml_compliance",
        "kyc_management",
        "om_account_followup",
        "accounting_pdf_reports",
    ],
    "data": [
        "views/business_reports_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
