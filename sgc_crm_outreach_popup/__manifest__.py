{
    'name': 'SGC CRM Outreach Popup',
    'version': '19.0.1.3.0',
    'category': 'CRM',
    'summary': 'Stage-change popup to choose Research or Sales outreach email',
    'description': """
SGC CRM Outreach Popup
======================
Triggers a popup when a lead is moved to "Valid Contact" stage (from any
stage, in kanban or form view), presenting two options: Research
Participation or Sales Deck. Sends the chosen template once per lead
(outreach_mail_sent flag).
    """,
    'author': 'SGC Tech AI',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'depends': ['crm', 'base_automation'],
    'data': [
        'security/ir.model.access.csv',
        'views/outreach_wizard_views.xml',
        'data/outreach_automation.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sgc_crm_outreach_popup/static/src/js/outreach_popup_service.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
