# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

{
    "name": "Dynamic Financial Reports",
    "version": "19.0.1.0.0",
    "category": "Accounting/Reports",
    "summary": "Enterprise-grade dynamic financial reporting suite for Odoo 19",
    "description": """
        Dynamic Financial Reports - Enterprise Financial Intelligence Suite
        ================================================================

        This module provides a comprehensive suite of dynamic financial reports
        for Odoo 19, including:

        * Balance Sheet
        * Profit & Loss Statement
        * Cash Flow Statement
        * Trial Balance
        * General Ledger
        * Partner Ledger
        * Aged Receivable Report
        * Aged Payable Report
        * Tax Report

        Features:
        - Multi-company support with company-specific configurations
        - Flexible date range filtering with period comparison
        - Multi-level analytic account filtering
        - Excel (XLSX) export with formatted output
        - Configurable account type to financial statement mapping
        - Real-time report generation with caching support
        - SGC TECH AI branded enterprise UI/UX
        - Granular access control (User / Manager / Admin)
    """,
    "author": "SGC TECH AI",
    "company": "SGC TECH AI",
    "maintainer": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    "license": "OPL-1",
    "depends": [
        "account",
        "report_xlsx",
        "web",
        "analytic",
        "mail",
    ],
    "data": [
        "security/sgc_access_rights.xml",
        "security/ir.model.access.csv",
        "data/sgc_account_type_data.xml",
        "data/sgc_report_actions.xml",
        "views/sgc_report_templates.xml",
        "views/scheduled_report_views.xml",
        "views/budget_views.xml",
        "data/scheduled_report_data.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "sgc_dynamic_financial_report/static/src/scss/sgc_financial_report.scss",
            "sgc_dynamic_financial_report/static/src/scss/enterprise_filter_bar.scss",
            "sgc_dynamic_financial_report/static/src/js/enterprise_filter_bar.js",
            "sgc_dynamic_financial_report/static/src/js/enterprise_filter_bar.xml",
            "sgc_dynamic_financial_report/static/src/js/sgc_report_client_action.js",
            "sgc_dynamic_financial_report/static/src/js/sgc_report_client_action.xml",
            "sgc_dynamic_financial_report/static/src/js/drilldown_handler.js",
        ],
        # PDF export renders via wkhtmltopdf, which only ever loads the
        # `web.report_assets_common` bundle - NOT `web.assets_backend`.
        # Without this entry the PDF gets zero custom CSS (no borders,
        # no brand colors, no print rules), which is why it rendered as
        # unstyled/raw HTML.
        "web.report_assets_common": [
            "sgc_dynamic_financial_report/static/src/scss/sgc_financial_report.scss",
        ],
    },
    "post_init_hook": "post_init_hook_function",
    "installable": True,
    "application": True,
    "auto_install": False,
}