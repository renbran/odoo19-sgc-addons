# -*- coding: utf-8 -*-
# SGC CRM Fields — signature pipeline custom fields for crm.lead.
# Deployed to odoo19-sgc (app.sgctech.ai) — see 10-signature/ADMIN-OPERATIONS-MANUAL.md.

{
    'name': 'SGC CRM Fields (Signature Pipeline)',
    'version': '19.0.1.0.0',
    'summary': 'Custom crm.lead fields consumed by the Zoho Sign webhook handler write-back (see 10-signature/odoo-mapping.yaml).',
    'description': """
Adds the 17 custom fields on crm.lead required by the SGC signature pipeline
(10-signature/odoo-mapping.yaml). The webhook handler writes these fields via
the Odoo External API (JSON-RPC 2.0) on sent / completed / declined / expired /
voided events.

Reference implementation — port to odoo19-sgc and review before production.
""",
    'author': 'SGC TECH AI / Scholarix Global Consultants FZCO',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'category': 'Sales/CRM',
    'depends': ['base', 'crm', 'account'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'application': False,
}
