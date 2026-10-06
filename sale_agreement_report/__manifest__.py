# -*- coding: utf-8 -*-
{
    'name': 'Sale Agreement Report',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Manage yearly SaaS subscription agreements with portal download and document upload',
    'description': """
Sale Agreement Report - SGC TECH AI
====================================
Intelligent Infrastructure. Instant Impact.

This module provides:
- Sales order agreement metadata for SaaS contracting
- Yearly customer agreement records
- Portal agreement download anytime for customers
- Portal upload and replacement of license and owner documents
- SaaS subscription agreement PDF templates
- Migration support from legacy sales-order agreement data
    """,
    'author': 'SGC TECH AI',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'depends': [
        'sale',
        'sale_management',
        'web',
        'website',
        'portal',
    ],
    'data': [
        'data/sale_agreement_sequence.xml',
        'security/sale_agreement_security.xml',
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/sale_agreement_views.xml',
        'views/portal_templates.xml',
        'report/sale_agreement_report.xml',
        'report/sale_agreement_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
