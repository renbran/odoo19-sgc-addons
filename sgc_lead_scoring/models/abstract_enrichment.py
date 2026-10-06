import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AbstractEnrichment(models.AbstractModel):
    _name = 'abstract.enrichment'
    _description = 'Abstract API Company Enrichment Service'

    API_URL = 'https://companyenrichment.abstractapi.com/v2'

    def _get_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'sgc_lead_scoring.abstract_api_key', '')

    def enrich_company(self, domain):
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(
                _('Abstract API key not configured. Set it in Settings > General Settings > Abstract API Key.'))

        if not domain:
            raise UserError(_('Company domain is required for enrichment'))

        import re
        domain = re.sub(r'^https?://(www\.)?', '', domain.strip()).split('/')[0]
        if not domain:
            return {'success': False, 'error': 'Invalid domain'}

        try:
            resp = requests.get(
                self.API_URL,
                params={'api_key': api_key, 'domain': domain},
                headers={'Accept': 'application/json'},
                timeout=15,
            )
            if resp.status_code == 422:
                return {'success': False, 'error': 'API quota reached (free plan limit)', 'domain': domain}
            resp.raise_for_status()
            data = resp.json()

            return {
                'success': True,
                'domain': data.get('domain', domain),
                'company_name': data.get('company_name', ''),
                'description': data.get('description', ''),
                'logo': data.get('logo', ''),
                'year_founded': data.get('year_founded', ''),
                'industry': data.get('industry', ''),
                'employee_count': data.get('employee_count', ''),
                'employee_range': data.get('employee_range', ''),
                'annual_revenue': data.get('annual_revenue', ''),
                'revenue_range': data.get('revenue_range', ''),
                'street_address': data.get('street_address', ''),
                'city': data.get('city', ''),
                'state': data.get('state', ''),
                'country': data.get('country', ''),
                'phone_numbers': data.get('phone_numbers', []),
                'email_addresses': data.get('email_addresses', []),
                'type': data.get('type', ''),
                'tags': data.get('tags', []),
                'technologies': data.get('technologies', []),
                'linkedin_url': data.get('linkedin_url', ''),
                'facebook_url': data.get('facebook_url', ''),
                'twitter_url': data.get('twitter_url', ''),
                'instagram_url': data.get('instagram_url', ''),
                'crunchbase_url': data.get('crunchbase_url', ''),
            }
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if hasattr(e, 'response') else 0
            if status == 401:
                raise UserError(_('Abstract API key is invalid. Check your key in Settings.'))
            if status == 429:
                raise UserError(_('Abstract API rate limit exceeded (1 req/sec on free plan). Try again later.'))
            raise UserError(_('Abstract API error: %s') % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_('Abstract API request timed out'))
        except Exception as e:
            _logger.error('Abstract company enrichment error: %s', str(e))
            return {'success': False, 'error': str(e), 'domain': domain}

    def enrich_lead(self, lead):
        changes = {}
        company_result = {'success': False}

        # Pick the best domain available
        domain = lead.website
        if not domain and lead.email_from and '@' in lead.email_from:
            domain = lead.email_from.split('@')[1]
        if not domain and lead.partner_name:
            domain = lead.partner_name
        if not domain:
            return {'success': False, 'error': 'No website, email, or company name to enrich from'}

        company_result = self.enrich_company(domain)
        if not company_result.get('success'):
            return {'success': False, 'company': False, 'error': company_result.get('error', 'Unknown error')}

        to_update = {}

        # Map company fields to x_ fields
        industry = (company_result.get('industry', '') or '')
        employee_count_str = (company_result.get('employee_count', '') or '')
        employee_count = 0
        if employee_count_str:
            try:
                employee_count = int(employee_count_str)
            except ValueError:
                employee_count = 0

        annual_revenue = (company_result.get('annual_revenue', '') or '')
        revenue_range = (company_result.get('revenue_range', '') or '')
        display_revenue = revenue_range if revenue_range else (f'${annual_revenue}' if annual_revenue else '')

        technologies = company_result.get('technologies', []) or []

        if industry:
            to_update['x_company_industry'] = industry[:256]
        if employee_count:
            to_update['x_employee_count'] = employee_count
        if display_revenue:
            to_update['x_annual_revenue'] = display_revenue[:256]
        if technologies:
            to_update['x_tech_stack'] = ', '.join(technologies)
        if company_result.get('linkedin_url'):
            to_update['x_company_linkedin'] = company_result['linkedin_url'][:256]
        if company_result.get('twitter_url'):
            to_update['x_company_twitter'] = company_result['twitter_url'][:256]

        # Map to standard Odoo fields (only if empty)
        if not lead.partner_name and company_result.get('company_name'):
            to_update['partner_name'] = company_result['company_name'][:256]
        if not lead.phone:
            phones = company_result.get('phone_numbers', [])
            if phones:
                to_update['phone'] = phones[0][:32]
        if not lead.email_from:
            emails = company_result.get('email_addresses', [])
            if emails:
                to_update['email_from'] = emails[0][:256]
        if not lead.street and company_result.get('street_address'):
            to_update['street'] = company_result['street_address'][:128]
        if not lead.city and company_result.get('city'):
            to_update['city'] = company_result['city'][:128]
        if not lead.country_id and company_result.get('country'):
            country = self.env['res.country'].search([('name', 'ilike', company_result['country'])], limit=1)
            if country:
                to_update['country_id'] = country.id

        if not to_update:
            return {'success': True, 'company': True, 'fields_updated': [], 'note': 'Lead already up to date'}

        now = fields.Datetime.now()
        to_update['x_apollo_enrichment_status'] = 'enriched'
        to_update['x_apollo_last_enriched'] = now
        to_update['x_last_activity_date'] = now
        to_update['x_enriched_by'] = self.env.user.id
        to_update['x_assigned_date'] = lead.x_assigned_date or (lead.create_date.date() if lead.create_date else now.date())

        lead.write(to_update)
        return {
            'success': True,
            'company': True,
            'person': False,
            'fields_updated': list(to_update.keys()),
            'error': '',
        }
