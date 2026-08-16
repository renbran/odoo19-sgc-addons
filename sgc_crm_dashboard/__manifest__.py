# -*- coding: utf-8 -*-
################################################################################
#
#    SGC TECH AI — combined dashboard module.
#
#    Originally based on Cybrosys Technologies' "CRM Dashboard"
#    (C) 2023-TODAY Cybrosys Technologies (https://www.cybrosys.com),
#    AGPL-3. Subsequently merged with "CRM Executive Dashboard"
#    (C) 2024-2026 SGC TECH AI (https://sgctech.ai), LGPL-3.
#
#    The combined module is distributed under LGPL-3. Files whose
#    upstream origin is the Cybrosys module retain their AGPL-3 notice
#    and remain governed by AGPL-3 to the extent of the original
#    Cybrosys copyright. New files added by SGC TECH AI are LGPL-3.
#
################################################################################
{
    "name": "SGC CRM Dashboard",
    'version': '19.0.1.2.0',
    "category": "Sales/CRM",
    "summary": """Unified CRM dashboard — executive KPIs, charts, alerts, scheduled exports.""",
    "description": """
SGC CRM Dashboard
=================

A unified executive-grade CRM dashboard for Odoo 19. Combines:

* Executive KPI Overview (Cybrosys ``crm.dashboard`` model)
* Production executive renderer + 12 chart widgets
* Drill-down, saved filters, alert rules
* Scheduled report delivery (CSV / XLSX / PDF)
* Three-tier security (User / Manager / Executive)

URLs
----
* /crm-dashboard           - Main dashboard
* /crm-dashboard/executive - Executive view

Compatibility
-------------
* Odoo 19 Community & Enterprise
* PostgreSQL
    """,
    "author": "Cybrosys Technologies, SGC TECH AI",
    "maintainer": "SGC TECH AI",
    "company": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "support": "hello@sgctech.ai",
    'depends': [
        'base',
        'web',
        'crm',
        'sale_management',
        'mail',
        'portal',
        'website',
        'base_setup',
    ],
    'data': [
        # ---- Security ----
        'security/crm_dashboard_groups.xml',
        'security/crm_dashboard_security.xml',
        'security/ir.model.access.csv',
        # ---- Mail + objection defaults (Cybrosys origin) ----
        'data/mail_templates.xml',
        'data/crm_objection_data.xml',
        # ---- Executive defaults + cron ----
        'data/crm_dashboard_data.xml',
        'data/crm_lead_redistribution_data.xml',
        # ---- Views (Cybrosys origin — keep original ordering) ----
        'views/crm_objection_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_team_views.xml',
        'views/res_users_views.xml',
        'views/utm_campaign_views.xml',
        'views/big_screen.xml',
        # ---- Views (executive origin — append after Cybrosys) ----
        'views/crm_dashboard_views.xml',
        'views/crm_dashboard_charts.xml',
        'views/crm_dashboard_filters.xml',
        'views/crm_dashboard_alerts.xml',
        'views/crm_dashboard_reports.xml',
        'views/crm_dashboard_menu.xml',
        'views/crm_dashboard_templates.xml',
        'views/crm_dashboard_utm_views.xml',
    ],
    'demo': [
        'data/crm_dashboard_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Cybrosys origin — keep at top
            'sgc_crm_dashboard/static/src/css/dashboard.scss',
            'sgc_crm_dashboard/static/src/css/dashboard.css',
            'sgc_crm_dashboard/static/src/css/charts.css',
            'sgc_crm_dashboard/static/src/css/kpi.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_variables.css',
            'sgc_crm_dashboard/static/src/js/dashboard/crm_dashboard.js',
            'sgc_crm_dashboard/static/src/xml/crm_dashboard.xml',
            # Executive origin — appended
            'sgc_crm_dashboard/static/src/css/crm_dashboard_core.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_charts.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_kpi.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_dark_theme.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_responsive.css',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_variables.css',
            'sgc_crm_dashboard/static/src/js/crm_dashboard_vanilla.js',
        ],
        'website.assets_frontend': [
            'sgc_crm_dashboard/static/src/js/big_screen.js',
            'sgc_crm_dashboard/static/src/css/crm_dashboard_public.css',
        ],
    },
    "images": [
        "static/description/icon.png",
        "static/description/banner.jpg",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
