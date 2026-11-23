# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # LLM Provider Settings
    llm_provider_id = fields.Many2one(
        'llm.provider',
        string='Default LLM Provider',
        config_parameter='llm_lead_scoring.default_provider_id',
    )

    # Auto-enrichment Settings
    auto_enrich_enabled = fields.Boolean(
        string='Enable Auto-Enrichment',
        config_parameter='llm_lead_scoring.auto_enrich_enabled',
        help='Automatically enrich leads using scheduled action',
    )

    auto_enrich_new_leads = fields.Boolean(
        string='Auto-Enrich New Leads',
        config_parameter='llm_lead_scoring.auto_enrich_new_leads',
        help='Automatically enrich leads when they are created',
    )

    auto_enrich_on_update = fields.Boolean(
        string='Auto-Enrich on Update',
        config_parameter='llm_lead_scoring.auto_enrich_on_update',
        help='Re-enrich leads when key fields are updated',
    )

    # Research Settings
    enable_customer_research = fields.Boolean(
        string='Enable Customer Research',
        config_parameter='llm_lead_scoring.enable_customer_research',
        default=True,
        help='Use LLM to research customers from public sources',
    )

    # Web Research Settings (Google Custom Search)
    enable_web_research = fields.Boolean(
        string='Enable Live Web Research',
        config_parameter='llm_lead_scoring.enable_web_research',
        default=False,
        help='Use Google Custom Search API for real-time web research (Free: 100 queries/day)',
    )

    allow_third_party_search = fields.Boolean(
        string='Allow Third-Party Web Search',
        config_parameter='llm_lead_scoring.allow_third_party_search',
        default=False,
        help='Master kill switch. When off, only the self-hosted SearXNG provider may run.',
    )

    anonymize_company_names = fields.Boolean(
        string='Anonymize Company Names in Research Queries',
        config_parameter='llm_lead_scoring.anonymize_company_names',
        default=False,
        help='Hash company name before sending to any third-party provider; results are re-associated locally.',
    )

    anonymize_customer_names = fields.Boolean(
        string='Anonymize Customer Names in Lead Intelligence',
        config_parameter='llm_lead_scoring.anonymize_customer_names',
        default=False,
        help='Hash contact name, lead name, and company name before sending to any third-party search '
             'provider or LLM for the Lead Intelligence Engine; results are re-associated locally. '
             'Relationship and conversation intelligence sections will be weaker as a result, since the '
             'LLM never sees the real names.',
    )

    google_search_api_key = fields.Char(
        string='Google Custom Search API Key',
        config_parameter='llm_lead_scoring.google_search_api_key',
        help='Get free API key from: https://developers.google.com/custom-search/v1/overview',
    )

    google_search_engine_id = fields.Char(
        string='Search Engine ID',
        config_parameter='llm_lead_scoring.google_search_engine_id',
        help='Create free search engine at: https://programmablesearchengine.google.com/',
    )

    # Google Maps API Settings
    google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter='llm_lead_scoring.google_maps_api_key',
        help='API key for Google Maps Place API. Get from: https://console.cloud.google.com/apis/library/places-backend.googleapis.com',
    )

    enable_maps_research = fields.Boolean(
        string='Enable Google Maps Lookup',
        config_parameter='llm_lead_scoring.enable_maps_research',
        default=False,
        help='Look up business details from Google Maps (ratings, reviews, address)',
    )

    # Enhanced Research Settings
    enable_tech_analysis = fields.Boolean(
        string='Enable Tech Stack Analysis',
        config_parameter='llm_lead_scoring.enable_tech_analysis',
        default=True,
        help='Analyze company website for technology stack (CMS, analytics, marketing tools)',
    )

    enable_digital_presence = fields.Boolean(
        string='Enable Digital Presence Check',
        config_parameter='llm_lead_scoring.enable_digital_presence',
        default=True,
        help='Check company presence on LinkedIn, Facebook, and other platforms',
    )

    # Scoring Weights
    weight_completeness = fields.Float(
        string='Completeness Weight (%)',
        config_parameter='llm_lead_scoring.weight_completeness',
        default=30.0,
        help='Weight of information completeness in final score',
    )

    weight_clarity = fields.Float(
        string='Clarity Weight (%)',
        config_parameter='llm_lead_scoring.weight_clarity',
        default=40.0,
        help='Weight of requirement clarity in final score',
    )

    weight_engagement = fields.Float(
        string='Engagement Weight (%)',
        config_parameter='llm_lead_scoring.weight_engagement',
        default=30.0,
        help='Weight of engagement level in final score',
    )

    @api.onchange('weight_completeness', 'weight_clarity', 'weight_engagement')
    def _onchange_weights(self):
        """Ensure weights sum to 100%"""
        total = self.weight_completeness + self.weight_clarity + self.weight_engagement
        if abs(total - 100.0) > 0.01 and total > 0:
            # Auto-adjust to ensure 100%
            ratio = 100.0 / total
            self.weight_completeness = round(self.weight_completeness * ratio, 2)
            self.weight_clarity = round(self.weight_clarity * ratio, 2)
            self.weight_engagement = round(self.weight_engagement * ratio, 2)
