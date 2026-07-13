{
    'name': 'KYC Management',
    'author': 'SGC TECH AI',
    'website_alt': 'https://www.scholarixglobal.com',
    'website': 'https://www.sgctech.ai',
    'mobile': '+971-52-198-5231',
    'support': 'info@sgctech.ai',
        'version': '19.0.1.0.0',
    'summary': 'Know Your Customer application management with full compliance workflow',
    'category': 'Compliance',
    'depends': ['base', 'contacts', 'mail', 'portal', 'web', 'website', 'crm'],
    'data': [
        # ── Security (load order matters) ───────────────────────────
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rules.xml',
        # ── Migration compatibility placeholder ─────────────────────
        'data/legacy_security_compat.xml',
            # ── CRM Integration ────────────────────────────────────────
            'data/crm_data.xml',
        # ── Reports (must load before views that reference them) ────
        'reports/kyc_application_report.xml',
        'reports/kyc_approvals_summary_report.xml',
        # ── Wizard views (must be before approval views) ────────────
        'wizard/kyc_wizard_views.xml',
        # ── Views & actions (must be before menu) ───────────────────
        'views/kyc_application_views.xml',
        'views/kyc_approval_views.xml',
        'views/kyc_notification_views.xml',
        # ── Menus & actions ─────────────────────────────────────────
        'views/kyc_menu.xml',
        # ── Portal / frontend KYC form ───────────────────────────────
        'views/portal_kyc_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kyc_management/static/src/css/kyc_backend.css',
            'kyc_management/static/src/js/kyc_dashboard.js',
            'kyc_management/static/src/xml/kyc_dashboard.xml',
        ],
        'web.assets_frontend': [
            'kyc_management/static/src/js/jquery_find_guard.js',
            'kyc_management/static/src/js/kyc_signature.js',
        ],
        'website.assets_wysiwyg': [
            'kyc_management/static/src/js/jquery_find_guard.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
