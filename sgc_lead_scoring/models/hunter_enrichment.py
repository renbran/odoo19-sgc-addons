import logging
import re
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HunterEnrichment(models.AbstractModel):
    _name = 'hunter.enrichment'
    _description = 'Hunter.io Company Enrichment Service'

    API_URL = 'https://api.hunter.io/v2/companies/find'

    def _get_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'sgc_lead_scoring.hunter_api_key', '')

    def enrich_company(self, domain):
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(_('Hunter API key not configured. Set it in Settings > General Settings.'))

        if not domain:
            raise UserError(_('Company domain is required for enrichment'))

        domain = re.sub(r'^https?://(www\.)?', '', domain.strip()).split('/')[0]
        if not domain:
            return {'success': False, 'error': 'Invalid domain'}

        try:
            resp = requests.get(
                self.API_URL,
                params={'domain': domain, 'api_key': api_key},
                headers={'Accept': 'application/json'},
                timeout=15,
            )
            if resp.status_code == 401:
                raise UserError(_('Hunter API key is invalid.'))
            if resp.status_code == 404:
                return {'success': False, 'error': 'Company not found on Hunter'}
            if resp.status_code == 429:
                raise UserError(_('Hunter API rate limit exceeded. Try again later.'))
            resp.raise_for_status()
            data = resp.json().get('data', {})

            industry = ''
            cat = data.get('category', {}) or {}
            industry = cat.get('industry', '') or cat.get('industryGroup', '') or cat.get('sector', '') or ''

            tags = data.get('tags', []) or []
            if not industry and tags:
                industry = tags[0]

            linkedin = ''
            li = data.get('linkedin', {}) or {}
            if li.get('handle'):
                linkedin = f'https://www.linkedin.com/{li["handle"]}'

            twitter = ''
            tw = data.get('twitter', {}) or {}
            if tw.get('handle'):
                twitter = f'https://x.com/{tw["handle"]}'

            site = data.get('site', {}) or {}
            phones = site.get('phoneNumbers', []) or []
            emails = site.get('emailAddresses', []) or []

            geo = data.get('geo', {}) or {}
            loc = data.get('location', '') or ''

            return {
                'success': True,
                'domain': data.get('domain', domain),
                'company_name': data.get('name', ''),
                'description': data.get('description', ''),
                'industry': industry,
                'founded_year': data.get('foundedYear', ''),
                'city': geo.get('city', '') or (loc.split(',')[0].strip() if loc and ',' in loc else ''),
                'state': geo.get('state', '') or '',
                'country': geo.get('country', '') or '',
                'country_code': geo.get('countryCode', '') or '',
                'phone_numbers': phones,
                'email_addresses': emails,
                'tags': tags,
                'linkedin_url': linkedin,
                'twitter_url': twitter,
                'facebook_url': (data.get('facebook', {}) or {}).get('handle', '') or '',
                'logo': data.get('logo', '') or '',
                'type': data.get('type', '') or '',
            }
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if hasattr(e, 'response') else 0
            if status in (401, 403):
                raise UserError(_('Hunter API key is invalid. Check your key in Settings.'))
            if status == 429:
                raise UserError(_('Hunter API rate limit exceeded.'))
            raise UserError(_('Hunter API error: %s') % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_('Hunter API request timed out'))
        except Exception as e:
            _logger.error('Hunter enrichment error: %s', str(e))
            return {'success': False, 'error': str(e), 'domain': domain}

    def enrich_lead(self, lead):
        changes = {}
        domain = lead.website
        if not domain and lead.email_from and '@' in lead.email_from:
            domain = lead.email_from.split('@')[1]
        if not domain and lead.partner_name:
            domain = lead.partner_name
        if not domain:
            return {'success': False, 'error': 'No website, email, or company name'}

        company_result = self.enrich_company(domain)
        if not company_result.get('success'):
            return {'success': False, 'company': False, 'error': company_result.get('error', '')}

        to_update = {}

        if company_result.get('industry'):
            to_update['x_company_industry'] = company_result['industry'][:256]
        if company_result.get('linkedin_url'):
            to_update['x_company_linkedin'] = company_result['linkedin_url'][:256]
        if company_result.get('twitter_url'):
            to_update['x_company_twitter'] = company_result['twitter_url'][:256]

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
        if not lead.city and company_result.get('city'):
            to_update['city'] = company_result['city'][:128]
        if not lead.country_id and company_result.get('country'):
            country = self.env['res.country'].search([('name', 'ilike', company_result['country'])], limit=1)
            if not country and company_result.get('country_code'):
                country = self.env['res.country'].search([('code', '=', company_result['country_code'])], limit=1)
            if country:
                to_update['country_id'] = country.id

        if not to_update:
            return {'success': False, 'company': True, 'error': 'No new data to update'}

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
            'provider': 'Hunter.io',
        }
