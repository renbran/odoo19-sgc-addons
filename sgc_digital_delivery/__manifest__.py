# -*- coding: utf-8 -*-
{
    'name': 'SGC Digital Product Delivery',
    'version': '19.0.1.3.0',
    'category': 'Sales/Sales',
    'summary': 'Attach a file to any product — auto-download on confirmation + portal page',
    'description': """
SGC Digital Product Delivery
==============================
- Attach any file (ZIP, PDF, etc.) to a product via the backend
- On payment confirmation: file auto-downloads instantly in the browser
- Email with secure download link sent to buyer after payment
- Portal page /my/downloads — re-download purchased files anytime
- Works with all Odoo payment providers (Stripe, PayPal, Mollie, etc.)
- Files are served through a token-authenticated download endpoint — never exposed directly
- Manual "Resend Digital Products" button on sale orders (manager-only)
- Digital badge on website shop cards and product detail pages
- Portal users / public web visitors are blocked from direct attachment access via ir.rule
    """,
    'author': 'SGC TECH AI',
    'website': 'https://sgctech.ai',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'website_sale',
        'mail',
        'account',
        'portal',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/sgc_digital_security.xml',
        'data/mail_template_digital.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/portal_templates.xml',
        'views/website_shop_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'sgc_digital_delivery/static/src/css/digital_badge.css',
        ],
    },
    'images': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
