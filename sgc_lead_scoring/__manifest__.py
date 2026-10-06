# -*- coding: utf-8 -*-
{
    "name": "SGC - Lead Scoring",
    'version': '19.0.1.0.1',
    "category": "CRM",
    "summary": "AI-Powered Lead Scoring with Multi-LLM Support",
    "description": """
 SGC Lead Scoring Module
 ========================
 This module enhances Odoo CRM with AI-powered lead scoring capabilities:

 Features:
 ---------
 * Multi-LLM Provider Support (OpenAI, Groq, HuggingFace, Anthropic, etc.)
 * Automated customer research from publicly available sources
 * AI-driven lead probability scoring based on:
   - Form completeness
   - Requirement clarity
   - Customer activity/intervention logs
 * Enrichment data logging in internal notes
 * Real-time and scheduled lead enrichment
 * Configurable scoring algorithms
 * Customizable LLM prompts and parameters

 The module leverages LLM reasoning capabilities to help sales teams:
 - Properly allocate efforts based on lead quality
 - Get enhanced customer insights
 - Improve conversion rates
 - Automate lead qualification

     """,
    "author": "SmartClinic",
    "website": "https://smartclinic.ae",
    "license": "LGPL-3",
    "depends": [
        "base",
        "crm",
        "mail",
    ],
    "data": [
        "security/llm_provider_security.xml",
        "security/ir.model.access.csv",
        "data/llm_provider_data.xml",
        "data/ir_cron_data.xml",
        "wizards/lead_enrichment_wizard_views.xml",
        "wizards/google_search_setup_wizard_views.xml",
        "views/llm_provider_views.xml",
        "views/res_config_settings_views.xml",
        "views/crm_lead_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sgc_lead_scoring/static/src/scss/lead_scoring.scss",
        ],
    },
    "external_dependencies": {
        "python": ["requests"],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "auto_install": False,
    "application": False,
}
