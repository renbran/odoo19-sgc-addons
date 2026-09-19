{
    "name": "SGC Report Theme - Payroll Documents Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-points the Payslip Details and UAE WPS Payslip reports onto the SGC TECH AI theme.",
    "description": """
SGC Report Theme - Payroll Documents Bridge
==============================================

Bridge module for the two payslip documents:
- hr_payroll_community.report_payslipdetails (t-calls web.external_layout
  directly - same pattern as the other bridges)
- eh_uae_payroll_wps.report_payslipdetails_uae_wps (t-calls
  web.internal_layout, not web.external_layout - re-pointed the same way,
  swapping only the t-call attribute)

2026-09-19: corrected the second bullet above from "web.basic_layout" to
"web.internal_layout" - that was always wrong (confirmed by reading
eh_uae_payroll_wps/report/uae_payslip_report.xml directly: it never calls
web.basic_layout at all), and the matching bug in
views/payroll_reports_bridge.xml's xpath meant this module's second
template never actually took effect, and blocked any -u/-i registry
reload on this database for any module while it was installed.

Uninstalling this module reverts both to their stock layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "hr_payroll_community", "eh_uae_payroll_wps"],
    "data": [
        "views/payroll_reports_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
