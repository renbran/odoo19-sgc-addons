import json
import logging
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ApolloEnrichment(models.AbstractModel):
    _name = 'apollo.enrichment'
    _description = 'Apollo.io Enrichment Service'

    API_BASE = 'https://api.apollo.io/api/v1'

    def _get_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'sgc_lead_scoring.apollo_api_key', '')

    def enrich_company(self, domain):
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(_('Apollo.io API key not configured. Set it in Settings > General Settings > Apollo API Key.'))
        if not domain:
            raise UserError(_('Company domain is required for enrichment'))

        import re
        domain = re.sub(r'^https?://(www\.)?', '', domain.strip()).split('/')[0]

        try:
            resp = requests.get(
                f'{self.API_BASE}/organizations/enrich',
                params={'domain': domain},
                headers={
                    'X-Api-Key': api_key,
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache',
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            org = data.get('organization', {})
            return {
                'success': True,
                'domain': domain,
                'name': org.get('name', ''),
                'website': org.get('website_url', ''),
                'industry': org.get('industry', ''),
                'estimated_num_employees': org.get('estimated_num_employees', 0),
                'revenue_range': org.get('revenue_range', ''),
                'revenue': org.get('annual_revenue', 0),
                'total_funding': org.get('total_funding', 0),
                'latest_funding_round': org.get('latest_funding_round', ''),
                'latest_funding_stage': org.get('latest_funding_stage', ''),
                'founded_year': org.get('founded_year', 0),
                'phone': org.get('phone', ''),
                'street': org.get('street_address', ''),
                'city': org.get('city', ''),
                'state': org.get('state', ''),
                'country': org.get('country', ''),
                'linkedin_url': org.get('linkedin_url', ''),
                'twitter_url': org.get('twitter_url', ''),
                'facebook_url': org.get('facebook_url', ''),
                'crunchbase_url': org.get('crunchbase_url', ''),
                'technologies': org.get('technologies', []),
                'seo_description': org.get('seo_description', ''),
                'short_description': org.get('short_description', ''),
                'current_employee_estimate': org.get('current_employee_estimate', 0),
            }
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if hasattr(e, 'response') else 0
            if status == 401:
                raise UserError(_('Apollo API key is invalid. Check your key in Settings.'))
            if status == 404:
                return {'success': False, 'error': 'Company not found on Apollo', 'domain': domain}
            if status == 422:
                body = e.response.text if hasattr(e, 'response') else ''
                err_msg = body or str(e)
                _logger.warning('Apollo enrich_company 422 for domain %s: %s', domain, err_msg)
                if 'insufficient credits' in err_msg.lower() or 'credits' in err_msg.lower():
                    return {'success': False, 'error': 'Apollo credits exhausted — upgrade at apollo.io', 'domain': domain}
                if 'can`t find' in err_msg.lower() or 'cannot enrich' in err_msg.lower():
                    return {'success': False, 'error': 'Company not found on Apollo', 'domain': domain}
                return {'success': False, 'error': 'Apollo API error: %s' % err_msg[:200], 'domain': domain}
            if status == 429:
                raise UserError(_('Apollo API rate limit exceeded. Try again later.'))
            raise UserError(_('Apollo API error: %s') % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_('Apollo API request timed out'))
        except Exception as e:
            _logger.error('Apollo company enrichment error: %s', str(e))
            return {'success': False, 'error': str(e), 'domain': domain}

    def enrich_person(self, email=None, domain=None, linkedin_url=None, first_name=None, last_name=None):
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(_('Apollo.io API key not configured.'))

        if not email and not linkedin_url:
            raise UserError(_('Email or LinkedIn URL required for person enrichment'))

        payload = {}
        if email:
            payload['email'] = email.strip()
        if domain:
            payload['domain'] = domain.strip()
        if linkedin_url:
            payload['linkedin_url'] = linkedin_url.strip()
        if first_name:
            payload['first_name'] = first_name.strip()
        if last_name:
            payload['last_name'] = last_name.strip()

        try:
            resp = requests.post(
                f'{self.API_BASE}/people/match',
                json=payload,
                headers={
                    'X-Api-Key': api_key,
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache',
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            person = data.get('person', {})
            return {
                'success': True,
                'first_name': person.get('first_name', ''),
                'last_name': person.get('last_name', ''),
                'name': '%s %s' % (person.get('first_name', ''), person.get('last_name', '')).strip(),
                'email': person.get('email', ''),
                'phone': person.get('phone', ''),
                'mobile_phone': person.get('mobile_phone', ''),
                'title': person.get('title', ''),
                'seniority': person.get('seniority', ''),
                'department': person.get('department', ''),
                'function': person.get('function', ''),
                'linkedin_url': person.get('linkedin_url', ''),
                'twitter_url': person.get('twitter_url', ''),
                'facebook_url': person.get('facebook_url', ''),
                'headline': person.get('headline', ''),
                'city': person.get('city', ''),
                'state': person.get('state', ''),
                'country': person.get('country', ''),
                'email_status': person.get('email_status', ''),
                'organization_name': person.get('organization_name', ''),
                'organization_domain': person.get('organization_domain', ''),
            }
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if hasattr(e, 'response') else 0
            if status == 401:
                raise UserError(_('Apollo API key is invalid.'))
            if status == 403:
                _logger.warning('Apollo person enrichment not available: free plan restriction')
                return {'success': False, 'error': 'Not available on your plan (upgrade at apollo.io)'}
            if status == 404:
                return {'success': False, 'error': 'Person not found on Apollo'}
            if status == 422:
                return {'success': False, 'error': 'Person not found on Apollo'}
            if status == 429:
                raise UserError(_('Apollo API rate limit exceeded.'))
            raise UserError(_('Apollo API error: %s') % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_('Apollo API request timed out'))
        except Exception as e:
            _logger.error('Apollo person enrichment error: %s', str(e))
            return {'success': False, 'error': str(e)}

    def enrich_lead(self, lead):
        changes = {}
        company_result = {'success': False}
        person_result = {'success': False}

        domain = lead.website
        if not domain and lead.email_from and '@' in lead.email_from:
            domain = lead.email_from.split('@')[1]
        if not domain and lead.partner_name:
            domain = lead.partner_name

        if domain:
            company_result = self.enrich_company(domain)
            if company_result.get('success'):
                to_update = {
                    'x_company_industry': (company_result.get('industry', '') or '')[:256],
                    'x_employee_count': company_result.get('current_employee_estimate', 0) or company_result.get('estimated_num_employees', 0) or 0,
                    'x_annual_revenue': company_result.get('revenue_range', '') or '',
                    'x_tech_stack': ', '.join(company_result.get('technologies', []) or []),
                    'x_funding_total': company_result.get('total_funding', 0) or 0,
                    'x_funding_stage': company_result.get('latest_funding_stage', '') or '',
                    'x_company_linkedin': (company_result.get('linkedin_url', '') or '')[:256],
                    'x_company_twitter': (company_result.get('twitter_url', '') or '')[:256],
                }
                changes.update(to_update)

                if not lead.partner_name and company_result.get('name'):
                    changes['partner_name'] = (company_result['name'])[:256]
                if not lead.phone and company_result.get('phone'):
                    changes['phone'] = (company_result['phone'])[:32]
                if not lead.street and company_result.get('street'):
                    changes['street'] = (company_result['street'])[:128]
                if not lead.city and company_result.get('city'):
                    changes['city'] = (company_result['city'])[:128]
                if not lead.country_id and company_result.get('country'):
                    country = self.env['res.country'].search([('name', 'ilike', company_result['country'])], limit=1)
                    if country:
                        changes['country_id'] = country.id

        if company_result.get('success'):
            person_result = self.enrich_person(
                email=lead.email_from,
                domain=lead.website or company_result.get('domain'),
            )
            if person_result.get('success'):
                to_update = {
                    'x_job_title': (person_result.get('title', '') or '')[:256],
                    'x_seniority': person_result.get('seniority', '') or '',
                    'x_department': (person_result.get('department', '') or '')[:128],
                    'x_person_linkedin': (person_result.get('linkedin_url', '') or '')[:256],
                    'x_email_verified': person_result.get('email_status', '') == 'verified',
                }
                changes.update(to_update)

                if not lead.contact_name and person_result.get('name'):
                    changes['contact_name'] = (person_result['name'])[:128]
                if not lead.email_from and person_result.get('email'):
                    changes['email_from'] = (person_result['email'])[:256]
                if not lead.phone and person_result.get('mobile_phone'):
                    changes['phone'] = (person_result['mobile_phone'])[:32]
                if not lead.function and person_result.get('function'):
                    changes['function'] = (person_result['function'])[:128]
                if not lead.country_id and person_result.get('country'):
                    if 'country_id' not in changes:
                        country = self.env['res.country'].search([('name', 'ilike', person_result['country'])], limit=1)
                        if country:
                            changes['country_id'] = country.id

        if changes:
            changes['x_apollo_enrichment_status'] = 'enriched'
            changes['x_apollo_last_enriched'] = fields.Datetime.now()
            lead.write(changes)
            return {
                'success': True,
                'company': company_result.get('success', False),
                'person': person_result.get('success', False),
                'fields_updated': list(changes.keys()),
            }

        lead.write({'x_apollo_enrichment_status': 'failed'})
        return {
            'success': False,
            'company': company_result.get('success', False),
            'person': person_result.get('success', False),
            'error': 'No data could be enriched',
        }
