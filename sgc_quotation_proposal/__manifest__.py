# -*- coding: utf-8 -*-
{
    'name': 'SGC - Quotation Proposal Report',
    'version': '19.0.1.1.0',
    'category': 'Sales',
    'summary': 'Premium branded proposal PDF for quotations (navy & gold design, UAE-landmark watermark)',
    'description': """
Quotation Proposal Report - SGC TECH AI
=======================================
Adds a "Commercial Proposal" print option on quotations / sales orders.

- Executive cover page with client and proposal metadata
- Scope of work table driven by the order lines (sections and notes supported)
- Investment summary with totals and payment terms
- Signature and acceptance block
- Print-ready A4 layout with SGC navy & gold design language
- UAE-identity watermark: faint composite line art of Burj Khalifa,
  Burj Al Arab and Sheikh Zayed Grand Mosque (6% opacity, centered)
    """,
    'author': 'SGC TECH AI',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'support': 'support@sgctech.ai',
    'depends': [
        'sale',
        'sale_management',
    ],
    'data': [
        'report/quotation_proposal_report.xml',
        'report/quotation_proposal_template.xml',
    ],
    'installable': False,  # RETIRED 2026-08-15 Phase 15 item 4b - superseded by sgc_proposal_engine governance
    'application': False,
    'auto_install': False,
}
