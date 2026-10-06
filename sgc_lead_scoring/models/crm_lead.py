import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    ai_probability_score = fields.Float(
        string='AI Probability Score',
        group_operator='avg',
        help='AI-calculated probability score based on lead quality (0-100)',
    )
    ai_completeness_score = fields.Float(
        string='Completeness Score',
        help='Score based on how complete the lead information is (0-100)',
    )
    ai_clarity_score = fields.Float(
        string='Clarity Score',
        help='Score based on requirement clarity (0-100)',
    )
    ai_engagement_score = fields.Float(
        string='Engagement Score',
        help='Score based on engagement level (0-100)',
    )
    ai_enrichment_status = fields.Selection([
        ('pending', 'Pending'),
        ('scored', 'Scored'),
        ('failed', 'Failed'),
        ('enriched', 'Enriched'),
    ], string='AI Enrichment Status', default='pending')
    ai_last_enrichment_date = fields.Datetime(
        string='Last AI Enrichment',
        readonly=True,
    )
    ai_enrichment_report = fields.Html(
        string='AI Enrichment Report',
        readonly=True,
        sanitize=True,
        sanitize_attributes=False,
        strip_classes=False,
    )
    ai_analysis_summary = fields.Text(
        string='AI Analysis Summary',
        readonly=True,
    )
    ai_enrichment_data = fields.Text(
        string='Raw Enrichment Data (JSON)',
        readonly=True,
    )
    auto_enrich = fields.Boolean(
        string='Auto-Enrich',
        default=True,
        help='Enable automatic AI enrichment for this lead',
    )
    ai_score_color = fields.Float(
        string='Score Color',
        compute='_compute_ai_score_color',
        store=True,
    )
    auto_enrich_global_enabled = fields.Boolean(
        string='Global Auto-Enrich Enabled',
        compute='_compute_auto_enrich_global',
        help='Whether global auto-enrichment is enabled in settings',
    )

    # Apollo/Abstract enrichment data fields
    x_apollo_enrichment_status = fields.Selection([
        ('pending', 'Pending'),
        ('enriched', 'Enriched'),
        ('failed', 'Failed'),
    ], string='Apollo Status')
    x_apollo_last_enriched = fields.Datetime(
        string='Last Apollo Enrichment', readonly=True)
    x_enriched_by = fields.Many2one(
        'res.users', string='Enriched By', readonly=True)
    x_job_title = fields.Char(string='Job Title')
    x_seniority = fields.Selection([
        ('owner', 'Owner'),
        ('c_suite', 'C-Suite'),
        ('vp', 'VP / SVP'),
        ('director', 'Director'),
        ('manager', 'Manager'),
        ('senior', 'Senior / IC'),
        ('entry', 'Entry Level'),
        ('intern', 'Intern'),
    ], string='Seniority Level')
    x_department = fields.Char(string='Department')
    x_email_verified = fields.Boolean(string='Email Verified')
    x_person_linkedin = fields.Char(string='LinkedIn Profile')
    x_mobile_phone = fields.Char(string='Mobile Phone')
    x_whatsapp = fields.Char(string='WhatsApp')
    x_company_industry = fields.Char(string='Industry')
    x_employee_count = fields.Integer(string='Employee Count')
    x_annual_revenue = fields.Char(string='Annual Revenue')
    x_funding_total = fields.Float(string='Total Funding (USD)')
    x_funding_stage = fields.Char(string='Funding Stage')
    x_tech_stack = fields.Text(string='Tech Stack')
    x_company_linkedin = fields.Char(string='Company LinkedIn')
    x_company_twitter = fields.Char(string='Company Twitter')
    x_scored_by = fields.Many2one(
        'res.users', string='Scored By', readonly=True)
    x_assigned_date = fields.Date(
        string='Assigned Date', readonly=True)
    x_last_activity_date = fields.Datetime(string='Last Activity Date')
    x_industry_fit = fields.Selection([
        ('high', 'High Fit'),
        ('medium', 'Medium Fit'),
        ('low', 'Low Fit'),
        ('unknown', 'Unknown'),
    ], string='Industry Fit')
    x_territory = fields.Selection([
        ('Dubai', 'Dubai'),
        ('Abu Dhabi', 'Abu Dhabi'),
        ('Northern Emirates', 'Northern Emirates'),
        ('International', 'International'),
    ], string='Territory')
    x_emirate = fields.Selection([
        ('Dubai', 'Dubai'),
        ('Abu Dhabi', 'Abu Dhabi'),
        ('Sharjah', 'Sharjah'),
        ('Ajman', 'Ajman'),
        ('Al Ain', 'Al Ain'),
        ('Ras Al Khaimah', 'Ras Al Khaimah'),
        ('Fujairah', 'Fujairah'),
        ('Umm Al Quwain', 'Umm Al Quwain'),
    ], string='Emirate')
    x_contact_authority = fields.Selection([
        ('c_suite', 'C-Suite / Owner'),
        ('director', 'Director / VP'),
        ('manager', 'Manager'),
        ('ic', 'Individual Contributor'),
        ('unknown', 'Unknown'),
    ], string='Contact Authority')
    x_last_contact_date = fields.Date(string='Last Contact Date')
    x_days_since_activity = fields.Integer(
        string='Days Since Activity', readonly=True)
    x_location_score = fields.Integer(string='Location Score')
    x_sales_play = fields.Char(
        string='Sales Play', readonly=True)
    x_geo_city = fields.Char(
        string='Geocoded City', readonly=True)

    # BANT fields for call notes
    x_bant_budget = fields.Text(string='Budget')
    x_bant_authority = fields.Text(string='Authority')
    x_bant_need = fields.Text(string='Need')
    x_bant_timeline = fields.Text(string='Timeline')

    @api.depends('ai_probability_score')
    def _compute_ai_score_color(self):
        for lead in self:
            score = lead.ai_probability_score or 0
            if score >= 70:
                lead.ai_score_color = 3
            elif score >= 40:
                lead.ai_score_color = 2
            else:
                lead.ai_score_color = 1

    @api.depends()
    def _compute_auto_enrich_global(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'llm_lead_scoring.auto_enrich_enabled', 'False') == 'True'
        for lead in self:
            lead.auto_enrich_global_enabled = enabled

    def _enrich_lead(self):
        self.ensure_one()
        if not self.auto_enrich:
            return

        # Rate limit: skip if enriched in last 24 hours
        if self.ai_last_enrichment_date:
            hours_since = (fields.Datetime.now() - self.ai_last_enrichment_date).total_seconds() / 3600
            if hours_since < 24 and self.ai_enrichment_status == 'enriched':
                _logger.info('Skipping lead %s - enriched %s hours ago', self.id, hours_since)
                return

        llm_service = self.env['llm.service']
        provider = self.env['llm.provider'].get_default_provider()
        if not provider:
            _logger.warning('No LLM provider configured for lead enrichment')
            return

        try:
            research_data = {}
            if self.env['ir.config_parameter'].sudo().get_param(
                    'llm_lead_scoring.enable_customer_research', 'True') == 'True':
                research_result = llm_service.research_customer(self, provider)
                research_data['customer_research'] = research_result

            scoring_success = llm_service.score_lead(self, provider)
            if not scoring_success:
                self.ai_enrichment_status = 'failed'
                return

            enrichment_parts = []
            if research_data.get('customer_research'):
                enrichment_parts.append({
                    'type': 'customer_research',
                    'data': research_data['customer_research'],
                })

            self.write({
                'ai_enrichment_data': json.dumps(enrichment_parts) if enrichment_parts else False,
                'ai_enrichment_status': 'enriched' if enrichment_parts else 'scored',
                'ai_last_enrichment_date': fields.Datetime.now(),
            })

            report = self._generate_enrichment_report()
            if report:
                self.ai_enrichment_report = report

            # Also run cascade enrichment (Apollo/Abstract/Hunter) if available
            try:
                cascade = self.env['lead.enrichment.cascade']
                cascade.enrich_lead(self)
            except KeyError:
                pass

            # Post a clean plain-text internal note (full report is in ai_enrichment_report field)
            try:
                score = self.ai_probability_score or 0
                score_label = 'High' if score >= 70 else ('Medium' if score >= 40 else 'Low')
                summary = self.ai_analysis_summary or ''
                provider_name = getattr(provider, 'name', 'LLM')
                user_name = self.env.user.display_name
                body = (
                    'AI Enrichment Complete — enriched by %s via %s\n'
                    'Score: %.0f / 100 (%s)'
                    '%s'
                ) % (
                    user_name, provider_name, score, score_label,
                    ('\n%s' % summary) if summary else '',
                )
                author_partner = self.env.user.partner_id.id if (self.env.user and self.env.user.partner_id) else False
                subtype = self.env.ref('mail.mt_note')
                self.message_post(body=body, subject='AI Enrichment', subtype_id=subtype.id if subtype else False, author_id=author_partner)
            except Exception:
                _logger.exception('Failed to post enrichment note for lead %s', self.id)

        except Exception as e:
            _logger.error('Lead enrichment failed for %s: %s', self.name, str(e))
            self.write({
                'ai_enrichment_status': 'failed',
                'ai_last_enrichment_date': fields.Datetime.now(),
            })

    def _generate_enrichment_report(self):
        self.ensure_one()
        if not self.ai_enrichment_data:
            return False

        score = self.ai_probability_score or 0
        score_color = 'success' if score >= 70 else ('warning' if score >= 40 else 'danger')
        score_label = 'High' if score >= 70 else ('Medium' if score >= 40 else 'Low')

        report = """
        <div class="ai-enrichment-report" style="font-family: Arial, sans-serif; padding: 15px; background: #f8f9fa; border-radius: 8px;">
            <h4 style="color: #333; margin-bottom: 15px;">AI Enrichment Report</h4>
            <div style="display: flex; gap: 20px; margin-bottom: 20px;">
                <div style="flex: 1; text-align: center; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="font-size: 36px; font-weight: bold; color: %s;">%.0f</div>
                    <div style="font-size: 12px; color: #666;">AI Score (%s)</div>
                </div>
            </div>
            <div style="margin-bottom: 15px;">
                <p style="margin: 5px 0; color: #555;">%s</p>
            </div>
        </div>
        """ % (
            '#28a745' if score >= 70 else ('#ffc107' if score >= 40 else '#dc3545'),
            score,
            score_label,
            self.ai_analysis_summary or '',
        )
        return report

    def action_enrich_with_ai(self):
        """Unified enrichment action - works for single or multiple leads"""
        return self._action_enrich_unified()

    def _action_enrich_unified(self):
        """Unified enrichment logic for single or multiple leads"""
        provider = self.env['llm.provider'].get_default_provider()
        if not provider:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Configuration Required'),
                    'message': _('No LLM provider configured. Please configure a provider in Settings > LLM Lead Scoring.'),
                    'type': 'warning',
                    'sticky': True,
                }
            }

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for lead in self:
            if not lead.auto_enrich:
                skipped_count += 1
                continue
            try:
                lead._enrich_lead()
                success_count += 1
            except Exception as e:
                _logger.error('Enrichment failed for lead %s: %s', lead.name, str(e))
                failed_count += 1

        # Build result message
        messages = []
        if success_count:
            messages.append(_('%d lead(s) enriched successfully') % success_count)
        if failed_count:
            messages.append(_('%d failed') % failed_count)
        if skipped_count:
            messages.append(_('%d skipped (auto-enrich disabled)') % skipped_count)

        msg_type = 'success' if failed_count == 0 and success_count > 0 else ('warning' if success_count > 0 else 'danger')
        message = '; '.join(messages) if messages else _('No leads were processed')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('AI Enrichment Complete'),
                'message': message,
                'type': msg_type,
                'sticky': False,
            }
        }

    def action_regenerate_report(self):
        self.ensure_one()
        if self.ai_enrichment_data:
            report = self._generate_enrichment_report()
            if report:
                self.ai_enrichment_report = report
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report Generated'),
                'message': _('Enrichment report has been regenerated.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_enrich_leads(self):
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            'llm_lead_scoring.auto_enrich_enabled', 'False') == 'True'
        if not enabled:
            return

        provider = self.env['llm.provider'].get_default_provider()
        if not provider:
            _logger.warning('Auto-enrichment cron skipped: no LLM provider configured')
            return

        leads = self.search([
            ('auto_enrich', '=', True),
            '|',
            ('ai_enrichment_status', '=', False),
            ('ai_enrichment_status', '=', 'pending'),
            ('ai_enrichment_status', '=', 'failed'),
        ], limit=20)

        # Filter: skip leads enriched in last 24 hours
        now = fields.Datetime.now()
        filtered = self.env['crm.lead']
        for lead in leads:
            if not lead.ai_last_enrichment_date:
                filtered |= lead
            else:
                hours_since = (now - lead.ai_last_enrichment_date).total_seconds() / 3600
                if hours_since >= 24:
                    filtered |= lead
        leads = filtered

        for lead in leads:
            try:
                lead._enrich_lead()
            except Exception as e:
                _logger.error('Auto-enrichment failed for lead %s: %s', lead.id, str(e))
                continue

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        auto_enrich = self.env['ir.config_parameter'].sudo().get_param(
            'llm_lead_scoring.auto_enrich_new_leads', 'False') == 'True'
        if auto_enrich:
            # Limit to max 10 new leads per batch to avoid rate limits
            for lead in leads[:10]:
                try:
                    lead._enrich_lead()
                except Exception:
                    continue
        return leads

    def write(self, vals):
        res = super().write(vals)
        if vals.get('name') or vals.get('partner_name') or vals.get('description') or vals.get('email_from'):
            auto_update = self.env['ir.config_parameter'].sudo().get_param(
                'llm_lead_scoring.auto_enrich_on_update', 'False') == 'True'
            if auto_update:
                for lead in self:
                    if lead.auto_enrich:
                        # Only enrich if not enriched in last 24 hours or failed
                        hours_since = 999
                        if lead.ai_last_enrichment_date:
                            hours_since = (fields.Datetime.now() - lead.ai_last_enrichment_date).total_seconds() / 3600
                        if hours_since >= 24 or lead.ai_enrichment_status == 'failed':
                            try:
                                lead._enrich_lead()
                            except Exception:
                                continue
        return res


