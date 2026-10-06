{
    'name': 'Customer/Supplier Payment Statement Report',
    'version': '19.0.1.0.0',
    'category': 'Productivity',
    'summary': "Generate and manage Customer and Supplier Payment Statement Reports with auto-sending and sharing features.",
    'description': """
        This module provides tools to generate Customer and Supplier Payment Statement Reports. 
        Features include:
        - Automatic monthly statements sent to customers.
        - Options to share PDF and Excel reports.
        - Easy management of payment statements directly from Odoo.
    """,
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': "https://www.cybrosys.com",
    'depends': ['base', 'account', 'contacts'],
    'data': [
        'data/ir_cron_data.xml',
        'views/res_partner_views.xml',
        'report/res_partner_reports.xml',
        'report/res_partner_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/statement_report/static/src/js/action_manager.js',
        ]
    },
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'auto_install': False,
    'installable': True,
    'application': False,
}
