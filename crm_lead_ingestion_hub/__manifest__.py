{
    'name': 'CRM Lead Ingestion Hub',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Ingest inbound webhook leads from Meta, Google Ads, LinkedIn, TikTok, Snapchat and generic sources into crm.lead',
    'description': """
CRM Lead Ingestion Hub
=======================
Secure, idempotent webhook ingestion of paid-ad-platform leads directly into
native crm.lead, with per-provider signature verification, deduplication,
native ir.cron retry/backoff, configurable field mapping and full audit
logging.
""",
    'author': 'SGC TECH',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'depends': ['crm', 'mail', 'utm'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/crm_lead_ingestion_log_views.xml',
        'views/crm_lead_source_config_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
