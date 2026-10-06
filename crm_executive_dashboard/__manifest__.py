# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

{
    'name': 'CRM Executive Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Premium Executive CRM KPI Dashboard with Real-time Analytics',
    'description': """
CRM Executive Dashboard
=======================

A premium executive CRM KPI dashboard providing real-time CRM performance monitoring,
sales productivity analytics, lead management insights, activity tracking, conversion metrics,
and executive-level reporting suitable for startups and growing businesses.

Features:
---------
* Executive KPI Overview (Leads, Opportunities, Revenue, Conversion)
* Sales Activity Analytics (Daily, Weekly, Monthly)
* Productivity Dashboard (Per User & Team)
* Startup Executive Metrics (Business Health, Growth, Pipeline Health)
* Lead Analytics (Source Analysis)
* Sales Funnel Visualization
* Executive Alert Center
* Interactive Charts (12 chart types)
* Advanced Filters (Date, Salesperson, Team, Source, Stage)
* Export (PDF, Excel, CSV)
* Scheduled Reports (Daily, Weekly, Monthly)
* Role-based Security (User, Manager, Executive)

URLs:
-----
* /crm-dashboard - Main Dashboard
* /crm-dashboard/executive - Executive View

Security Groups:
----------------
* CRM Dashboard User
* CRM Dashboard Manager
* CRM Dashboard Executive

Compatibility:
--------------
* Odoo 19 Community & Enterprise
* PostgreSQL
* Owl Framework
* Responsive Design (Desktop, Tablet, Mobile)
    """,
    'author': 'SGC TECH AI',
    'website': 'https://sgctech.ai',
    'support': 'hello@sgctech.ai',
    'maintainer': 'SGC TECH AI',
    'license': 'LGPL-3',
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
        'security/crm_dashboard_groups.xml',
        'security/crm_dashboard_security.xml',
        'security/ir.model.access.csv',
        'data/crm_dashboard_data.xml',
        'views/crm_dashboard_views.xml',
        'views/crm_dashboard_templates.xml',
        'views/crm_dashboard_charts.xml',
        'views/crm_dashboard_filters.xml',
        'views/crm_dashboard_alerts.xml',
        'views/crm_dashboard_reports.xml',
        'views/crm_dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'crm_executive_dashboard/static/src/css/crm_dashboard_variables.css',
            'crm_executive_dashboard/static/src/css/crm_dashboard_core.css',
            'crm_executive_dashboard/static/src/css/crm_dashboard_kpi.css',
            'crm_executive_dashboard/static/src/css/crm_dashboard_charts.css',
            'crm_executive_dashboard/static/src/css/crm_dashboard_responsive.css',
            'crm_executive_dashboard/static/src/css/crm_dashboard_dark_theme.css',
        ],
        'web.assets_frontend': [
            'crm_executive_dashboard/static/src/css/crm_dashboard_public.css',
        ],
    },
    'qweb': [],
    'demo': [
        'data/crm_dashboard_demo.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 10,
    'images': [
        'static/description/icon.png',
        'static/description/banner.png',
    ],
}