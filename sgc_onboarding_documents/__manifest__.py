# -*- coding: utf-8 -*-
{
    'name': 'SGC Onboarding Documents',
    'version': '19.0.1.1.0',
    'category': 'Human Resources',
    'summary': 'Public document-upload page for new hires — files land on the applicant chatter',
    'description': """
Public, token-based document upload form for onboarding candidates.
Files are validated server-side (PDF/PNG/JPG, 10 MB) and written as
`ir.attachment` records on the relevant `hr.applicant` record's chatter.

HR can generate, refresh and e-mail the upload link from the applicant form;
links expire after a configurable TTL (`sgc_onboarding.token_ttl_days`,
default 30 days).
""",
    'author': 'Scholarix Global Consultants',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_recruitment',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/email_templates.xml',
        'views/templates.xml',
        'views/hr_applicant_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}