# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LeadEnrichmentWizard(models.TransientModel):
    _name = 'lead.enrichment.wizard'
    _description = 'Lead Enrichment Wizard'

    lead_ids = fields.Many2many(
        'crm.lead',
        string='Leads',
        required=True,
    )

    provider_id = fields.Many2one(
        'llm.provider',
        string='LLM Provider',
        help='Leave empty to use default provider',
    )

    force_research = fields.Boolean(
        string='Force Customer Research',
        default=True,
        help='Research customer even if disabled in settings',
    )

    lead_count = fields.Integer(
        string='Number of Leads',
        compute='_compute_lead_count',
    )

    @api.depends('lead_ids')
    def _compute_lead_count(self):
        for wizard in self:
            wizard.lead_count = len(wizard.lead_ids)

    @api.model
    def default_get(self, fields_list):
        """Set default leads from context"""
        res = super(LeadEnrichmentWizard, self).default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['lead_ids'] = [(6, 0, active_ids)]

        return res

    def action_enrich_leads(self):
        """Enrich selected leads"""
        self.ensure_one()

        if not self.lead_ids:
            raise UserError(_('Please select at least one lead to enrich.'))

        # Check if provider is configured
        provider = self.provider_id or self.env['llm.provider'].get_default_provider()
        if not provider:
            raise UserError(_('No LLM provider configured. Please configure a provider first.'))

        # Enrich leads
        success_count = 0
        failed_count = 0

        for lead in self.lead_ids:
            try:
                lead._enrich_lead()
                success_count += 1
            except Exception as e:
                failed_count += 1
                continue

        # Show result notification
        if failed_count == 0:
            message = _('%d lead(s) enriched successfully!') % success_count
            msg_type = 'success'
        else:
            message = _('%d lead(s) enriched, %d failed.') % (success_count, failed_count)
            msg_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Lead Enrichment'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }
