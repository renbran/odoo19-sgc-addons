# -*- coding: utf-8 -*-
{
    'name': 'SGC Construction Management',
    'version': '19.0.1.2.9',
    'summary': 'Manage BOQ, WBS, Work Orders, Billing, Quality & more',
    'description': """
SGC Construction Management
================================
A comprehensive module for managing construction projects including:
- Construction Projects with smart buttons
- BOQ (Bill of Quantities) with line items
- WBS Phases (Work Breakdown Structure)
- Work Orders management
- Material Requisitions
- Subcontracting
- RA Billing (Running Account)
- Progress Billing
- Quality Checks with checklists
- Expenses tracking
- Document Management (DMS)
- Site Diary & Progress Reporting
- HSE & QAQC Tracking
- Transmittals
- UAE Contractor Style Reports
- OWL Dashboard
    """,
    'category': 'Construction',
    'author': 'SGC',
    'website': 'https://sgc-tech.ai',
    'support': 'support@sgc-tech.ai',
    'maintainer': 'SGC TECH AI',
    'depends': ['base', 'mail', 'product', 'uom', 'account', 'report_xlsx', 'portal', 'web'],
    'data': [
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        'data/construction_data.xml',
        'data/ir_sequence.xml',
        'data/construction_sequences.xml',
        'report/construction_report_layout.xml',
        'report/project_reports.xml',
        'report/project_soa_report_template.xml',
        'views/construction_project_views.xml',
        'views/construction_boq_views.xml',
        'views/construction_wbs_views.xml',
        'views/construction_work_order_views.xml',
        'views/construction_material_requisition_views.xml',
        'views/construction_purchase_order_views.xml',
        'views/construction_subcontract_views.xml',
        'views/construction_billing_views.xml',
        'views/construction_quality_check_views.xml',
        'views/construction_expense_views.xml',
        'views/construction_document_views.xml',
        'views/construction_site_management_views.xml',
        'views/construction_transmittal_views.xml',
        'views/construction_hse_views.xml',
        'views/construction_dashboard_views.xml',
        'views/construction_menu.xml',
        'views/portal_templates.xml',
        'report/construction_boq_report.xml',
        'report/construction_boq_report_template.xml',
        'report/construction_phase1_reports.xml',
        'report/construction_phase1_report_templates.xml',
        # Loaded after the reports above because it adds a menu under
        # menu_construction_reporting (defined in construction_phase1_reports.xml).
        'views/res_partner_views.xml',
        'report/construction_purchase_order_report.xml',
        'report/sgc_report_layout.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # ECharts (CDN) - small, used for the dashboard charts
            'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js',
            # Leaflet (locally bundled - interactive map library)
            'sgc_construction_management/static/lib/leaflet/leaflet.css',
            'sgc_construction_management/static/lib/leaflet/leaflet.js',
            # Module CSS and JS
            'sgc_construction_management/static/src/css/construction_dashboard.css',
            'sgc_construction_management/static/src/js/construction_dashboard.js',
            # OWL Templates
            'sgc_construction_management/static/src/xml/construction_dashboard.xml',
        ],
        'web.report_assets_common': [
            # SGC brand styling for construction-specific reports
            'sgc_construction_management/static/src/css/construction_report.css',
            # SGC brand styling for ALL standard Odoo reports (quotations, invoices, etc.)
            'sgc_construction_management/static/src/css/sgc_report.css',
        ],
    },
    'demo': ['demo/construction_demo.xml'],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'license': 'OPL-1',
    'price': 149,
    'currency': 'USD',
    'images': ['static/description/icon.png', 'static/description/screenshots/01_dashboard.jpg'],
}
