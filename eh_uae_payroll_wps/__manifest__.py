{
    'name': 'UAE WPS Payroll Compliance',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'summary': 'UAE Wages Protection System (WPS) compliance - SIF file generation',
    'description': """
UAE Wages Protection System (WPS) compliance for hr_payroll_community.

Adds:
- WPS Employee ID (MOHRE Labor Card Number)
- Agent ID (Bank routing code) and Routing Code
- IBAN for salary payment
- SIF (Standard Interface File) file generator wizard
- Individual UAE WPS Payslip PDF report
- WPS Batch Summary PDF report
- WPS reports and menu

Compliant with UAE MOHRE WPS specification v3.2.
    """,
    'author': 'SGC Construction',
    'license': 'LGPL-3',
    'depends': ['hr_payroll_community', 'hr', 'report_xlsx'],
    'data': [
        'security/ir.model.access.csv',
        'report/uae_payslip_report.xml',
        'report/wps_xlsx_report.xml',
        'views/hr_employee_views.xml',
        'views/hr_version_views.xml',
        'wizard/hr_wps_wizard_views.xml',
        'data/menu.xml',
    ],
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
}
