{
    'name': 'Scholarix Professional Reports',
    'version': '19.0.2.0.0',
    'category': 'Sales',
    'summary': 'SGC TECH AI branded quotation and invoice PDF reports',
    'description': 'Professional SGC-branded layout for sale order quotations '
                   'and account invoices. Uses proper inheritance to remain '
                   'compatible with all standard Odoo modules.',
    'author': 'Scholarix Global',
    'website': 'https://scholarixglobal.com',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'account'],
    'data': [
        'report/report_style.xml',
        'report/sale_order_report.xml',
        'report/account_invoice_report.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
