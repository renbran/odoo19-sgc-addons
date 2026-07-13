# -*- coding: utf-8 -*-
"""
SGC TECH AI — Theme Configuration

FIX Q2: Removed ambiguous double-inheritance.
         Correct Odoo pattern: inherit TransientModel implicitly via _inherit = 'res.config.settings'.
         The explicit `models.TransientModel` base class is removed.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SGCConfig(models.TransientModel):
    """
    SGC TECH AI Theme Configuration — extends res.config.settings in-place.
    Access via: Settings > Website > SGC TECH AI
    FIX Q2 / OC2: No _name — this is a class extension, not a new model.
    Adding _name would create a separate model that breaks the settings save/load
    cycle and requires its own ir.model.access.csv entry.  _inherit alone is
    the correct Odoo pattern for adding fields to an existing settings model.
    """
    # FIX Q2 / OC2: _inherit alone — no _name, no _description needed.
    _inherit = 'res.config.settings'

    # ─── AI COPILOT ───────────────────────────────────────

    sgc_anthropic_api_key = fields.Char(
        string='Anthropic API Key (Claude)',
        config_parameter='sgc_theme_ai.anthropic_api_key',
        help=(
            'Claude AI API key for the Copilot chat widget. '
            'Get yours at https://console.anthropic.com — '
            'key starts with sk-ant-api03-...'
        ),
    )

    sgc_copilot_enabled = fields.Boolean(
        string='Enable AI Copilot Widget',
        config_parameter='sgc_theme_ai.copilot_enabled',
        default=True,
    )

    sgc_copilot_name = fields.Char(
        string='Copilot Display Name',
        config_parameter='sgc_theme_ai.copilot_name',
        default='SGC Copilot',
    )

    # ─── CONTACT ──────────────────────────────────────────

    sgc_whatsapp_number = fields.Char(
        string='WhatsApp Number',
        config_parameter='sgc_theme_ai.whatsapp_number',
        default='+971 52 198 5231',
        help='Format: +971XXXXXXXXX (no spaces)',
    )

    sgc_whatsapp_message = fields.Char(
        string='WhatsApp Default Message',
        config_parameter='sgc_theme_ai.whatsapp_message',
        default=(
            "Hello SGC TECH AI! I'm interested in learning "
            "about your 14-day ERP implementation."
        ),
    )

    sgc_company_phone = fields.Char(
        string='Company Phone',
        config_parameter='sgc_theme_ai.company_phone',
        default='+971 52 198 5231',
    )

    sgc_company_email = fields.Char(
        string='Company Email',
        config_parameter='sgc_theme_ai.company_email',
        default='hello@sgctech.ai',
    )

    sgc_calendly_url = fields.Char(
        string='Calendly Booking URL',
        config_parameter='sgc_theme_ai.calendly_url',
        default='https://calendly.com/sgctech-ai/consultation',
    )

    # ─── ANALYTICS ────────────────────────────────────────

    sgc_google_analytics = fields.Char(
        string='Google Analytics 4 ID',
        config_parameter='sgc_theme_ai.ga_id',
        help='e.g. G-XXXXXXXXXX',
    )

    sgc_meta_pixel = fields.Char(
        string='Meta Pixel ID',
        config_parameter='sgc_theme_ai.meta_pixel',
    )

    # ─── STORE ────────────────────────────────────────────

    sgc_store_enabled = fields.Boolean(
        string='Enable SGC Store (store.sgctech.ai)',
        config_parameter='sgc_theme_ai.store_enabled',
        default=True,
    )

    # ─── BUSINESS PARAMETERS ──────────────────────────────

    sgc_min_roi_guarantee = fields.Integer(
        string='Minimum ROI Guarantee Display (%)',
        config_parameter='sgc_theme_ai.min_roi',
        default=150,
        help='Floor shown in marketing materials. Does not affect actual ROI calculations.',
    )

    sgc_implementation_days = fields.Integer(
        string='Implementation Days Claim',
        config_parameter='sgc_theme_ai.impl_days',
        default=14,
    )
