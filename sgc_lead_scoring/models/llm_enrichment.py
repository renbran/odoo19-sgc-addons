import json
import logging
import os
import requests
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LlmEnrichment(models.AbstractModel):
    _name = 'llm.enrichment'
    _description = 'LLM-Powered Company Enrichment (DDG Search + Groq)'

    def _get_groq_api_key(self):
        key = self.env['ir.config_parameter'].sudo().get_param(
            'sgc_lead_scoring.groq_api_key', '')
        if not key:
            key = os.environ.get('GROQ_API_KEY', '')
        return key

    def _search_company(self, company_name, website=None):
        try:
            from ddgs import DDGS
            query = company_name
            if website:
                query = f'{query} {website}'
            query += ' company UAE'
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=10))
            return results
        except Exception as e:
            _logger.error('DDG search failed: %s', str(e))
            return []

    def _call_groq(self, prompt, system_prompt=None):
        api_key = self._get_groq_api_key()
        if not api_key:
            raise UserError(_('GROQ_API_KEY not configured. Set it in Settings.'))

        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})

        try:
            resp = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                json={
                    'model': 'llama-3.1-8b-instant',
                    'messages': messages,
                    'temperature': 0.1,
                    'max_tokens': 1024,
                },
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data['choices'][0]['message']['content']
            return content
        except Exception as e:
            _logger.error('Groq LLM call failed: %s', str(e))
            raise UserError(_('LLM enrichment failed: %s') % str(e))

    def enrich_company(self, company_name, website=None):
        search_results = self._search_company(company_name, website)
        if not search_results:
            return {'success': False, 'error': 'No search results found for this company'}

        context = '\n\n'.join(
            f'Title: {r.get("title", "")}\nURL: {r.get("href", "")}\nSnippet: {r.get("body", "")}'
            for r in search_results
        )

        prompt = f"""Based on the web search results below, extract company information as JSON.
Return ONLY valid JSON with no markdown formatting or code blocks.

Extract these fields (use null for unknown):
- name (company name)
- industry
- description (brief company description)
- employee_count (integer, approximate)
- annual_revenue (string, e.g. "$10M-$50M")
- website
- linkedin_url
- twitter_url
- facebook_url
- phone
- street_address
- city
- country
- founding_year

Web search results for {company_name}:
{context[:4000]}
"""

        try:
            content = self._call_groq(prompt)
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                _logger.warning('No JSON found in Groq response: %s', content[:200])
                return {'success': False, 'error': 'Could not parse enrichment data'}

            return {
                'success': True,
                'name': data.get('name', company_name),
                'industry': str(data.get('industry') or ''),
                'description': str(data.get('description') or ''),
                'estimated_num_employees': data.get('employee_count') or 0,
                'annual_revenue': str(data.get('annual_revenue') or ''),
                'website': str(data.get('website') or ''),
                'linkedin_url': str(data.get('linkedin_url') or ''),
                'twitter_url': str(data.get('twitter_url') or ''),
                'facebook_url': str(data.get('facebook_url') or ''),
                'phone': str(data.get('phone') or ''),
                'street': str(data.get('street_address') or ''),
                'city': str(data.get('city') or ''),
                'country': str(data.get('country') or ''),
                'founded_year': data.get('founding_year') or 0,
            }
        except Exception as e:
            _logger.error('Groq enrichment parse error: %s', str(e))
            return {'success': False, 'error': str(e)}

    def enrich_lead(self, lead):
        changes = {}
        company_name = lead.partner_name or lead.contact_name or lead.name or ''
        website = lead.website or ''
        email_domain = ''
        if not website and lead.email_from and '@' in lead.email_from:
            email_domain = lead.email_from.split('@')[1]

        if not company_name and not website and not email_domain:
            return {'success': False, 'error': 'No company name, website, or email to search from'}

        company_result = self.enrich_company(company_name, website or email_domain)
        if not company_result.get('success'):
            return {'success': False, 'error': company_result.get('error', 'Unknown error')}

        industry = (company_result.get('industry', '') or '')
        if industry:
            changes['x_company_industry'] = industry[:256]
        emp = company_result.get('estimated_num_employees') or 0
        if emp:
            changes['x_employee_count'] = int(emp)
        revenue = (company_result.get('annual_revenue', '') or '')
        if revenue:
            changes['x_annual_revenue'] = revenue[:256]
        if company_result.get('linkedin_url'):
            changes['x_company_linkedin'] = company_result['linkedin_url'][:256]
        if company_result.get('twitter_url'):
            changes['x_company_twitter'] = company_result['twitter_url'][:256]

        if not lead.partner_name and company_result.get('name'):
            changes['partner_name'] = company_result['name'][:256]
        if not lead.phone and company_result.get('phone'):
            changes['phone'] = company_result['phone'][:32]
        if not lead.street and company_result.get('street'):
            changes['street'] = company_result['street'][:128]
        if not lead.city and company_result.get('city'):
            changes['city'] = company_result['city'][:128]
        if not lead.country_id and company_result.get('country'):
            country = self.env['res.country'].search([('name', 'ilike', company_result['country'])], limit=1)
            if country:
                changes['country_id'] = country.id
        if company_result.get('description') and not lead.description:
            changes['description'] = company_result['description'][:2048]

        if not changes:
            return {'success': False, 'company': True, 'error': 'No new data to update'}

        now = fields.Datetime.now()
        changes['x_apollo_enrichment_status'] = 'enriched'
        changes['x_apollo_last_enriched'] = now
        changes['x_last_activity_date'] = now
        changes['x_enriched_by'] = self.env.user.id
        changes['x_assigned_date'] = lead.x_assigned_date or (lead.create_date.date() if lead.create_date else now.date())
        lead.write(changes)

        return {
            'success': True,
            'company': True,
            'person': False,
            'fields_updated': list(changes.keys()),
        }
