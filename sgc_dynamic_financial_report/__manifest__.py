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
    ],
    "data": [
        "security/sgc_access_rights.xml",
        "security/ir.model.access.csv",
        "data/sgc_account_type_data.xml",
        "views/sgc_wizard_views.xml",
        "data/sgc_report_actions.xml",
        "views/sgc_report_templates.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "sgc_dynamic_financial_report/static/src/scss/sgc_financial_report.scss",
        ],
    },
    "post_init_hook": "post_init_hook_function",
    "installable": True,
    "application": True,
    "auto_install": False,
}