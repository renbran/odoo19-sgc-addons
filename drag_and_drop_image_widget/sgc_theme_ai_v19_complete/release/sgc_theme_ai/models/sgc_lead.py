# -*- coding: utf-8 -*-
"""
SGC TECH AI — Extended CRM Lead

Fixes applied:
  FIX Q1: Removed duplicate field declaration of sgc_roi_projection.
  FIX Q7: Replaced @api.onchange with @api.depends compute for sgc_package —
           onchange only fires in UI; compute fires on programmatic creation too.
"""

from odoo import models, fields, api


class SGCLead(models.Model):
    """Extended CRM lead capturing SGC-specific qualification data."""
    _inherit = 'crm.lead'

    # ─── SGC QUALIFICATION FIELDS ─────────────────────────

    sgc_employees = fields.Integer(
        string='Number of Employees',
        help='Team size for ROI calculation',
    )

    sgc_monthly_cost = fields.Float(
        string='Monthly Operational Cost (AED)',
        digits=(16, 2),
    )

    sgc_industry = fields.Selection([
        ('real_estate',           'Real Estate'),
        ('trading',               'Trading & Distribution'),
        ('manufacturing',         'Manufacturing'),
        ('professional_services', 'Professional Services'),
        ('hospitality',           'Hospitality'),
        ('other',                 'Other'),
    ], string='Industry')

    # FIX Q1: Single field definition — compute only, no duplicate readonly stub.
    sgc_roi_projection = fields.Float(
        string='Projected ROI (%)',
        digits=(5, 1),
        compute='_compute_roi',
        store=True,
        readonly=True,
        help='Auto-calculated based on industry multipliers. '
             'NOTE: Multipliers are illustrative estimates, not guaranteed outcomes.',
    )

    # FIX Q7: sgc_package is now a compute field, not onchange.
    # Fires on programmatic creation (e.g. Copilot API, ROI calculator webhook).
    sgc_package = fields.Selection([
        ('starter',    'Starter — AED 25,000'),
        ('growth',     'Growth — AED 45,000'),
        ('enterprise', 'Enterprise — AED 85,000'),
    ], string='Recommended Package',
       compute='_compute_package',
       store=True,
       readonly=False,  # Allow manual override in UI after compute
    )

    sgc_source = fields.Selection([
        ('website_form',   'Website Form'),
        ('roi_calculator', 'ROI Calculator'),
        ('copilot',        'AI Copilot'),
        ('whatsapp',       'WhatsApp'),
        ('referral',       'Referral'),
    ], string='SGC Lead Source', default='website_form')

    sgc_trial_interest = fields.Boolean(
        string='Interested in Free Trial',
        default=False,
    )

    sgc_consultation_notes = fields.Text(
        string='Pre-Consultation Notes',
    )

    # ─── COMPUTED FIELDS ──────────────────────────────────

    # NOTE: ROI multipliers below are illustrative estimates based on SGC deployment
    # averages. They are NOT guaranteed outcomes and should be disclosed as estimates.
    _ROI_MAP = {
        'real_estate':           175,
        'trading':               165,
        'manufacturing':         155,
        'professional_services': 185,
        'hospitality':           150,
    }

    @api.depends('sgc_industry', 'sgc_monthly_cost', 'sgc_employees')
    def _compute_roi(self):
        for rec in self:
            if rec.sgc_industry and rec.sgc_monthly_cost:
                base  = self._ROI_MAP.get(rec.sgc_industry, 150)
                scale = min(1.2, 1 + (rec.sgc_employees or 10) * 0.002)
                rec.sgc_roi_projection = round(base * scale, 1)
            else:
                rec.sgc_roi_projection = 0.0

    @api.depends('sgc_employees')
    def _compute_package(self):
        for rec in self:
            n = rec.sgc_employees or 0
            if n <= 0:
                rec.sgc_package = False
            elif n <= 15:
                rec.sgc_package = 'starter'
            elif n <= 50:
                rec.sgc_package = 'growth'
            else:
                rec.sgc_package = 'enterprise'
