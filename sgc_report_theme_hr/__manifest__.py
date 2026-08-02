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
  web.basic_layout, not web.external_layout - re-pointed the same way,
  swapping only the t-call attribute)

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
