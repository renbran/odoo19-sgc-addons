# -*- coding: utf-8 -*-
{
    'name': 'SGC Onboarding Documents',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Public document-upload page for new hires — files land on the applicant chatter',
    'description': """
Public, token-based document upload form for onboarding candidates.
Files are written as `mail.message` attachments on the relevant
`hr.applicant` record's chatter (the "log").
""",
    'author': 'Scholarix Global Consultants',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr_recruitment',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
