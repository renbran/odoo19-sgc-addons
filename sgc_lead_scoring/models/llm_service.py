import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are an expert B2B lead scoring analyst for a technology solutions company in the UAE.
Analyze this lead and provide scores based on B2B sales best practices.

Lead Information:
- Name: {name}
- Company: {company_name}
- Email: {email} (verified: {email_verified})
- Phone: {phone}
- Website: {website}
- Description: {description}
- Industry (enriched): {enriched_industry}
- Employee Count: {employee_count}
- Annual Revenue: {annual_revenue}
- Tech Stack: {tech_stack}
- Contact Person: {contact_name}
- Job Title: {job_title}
- Seniority: {seniority}
- Country: {country}
- Location/Emirate: {emirate}
- Territory: {territory}
- Lead Source: {source}
- Stage: {stage}

Customer Research Data:
{research_data}

Score each category from 0-100:

1. COMPLETENESS SCORE: How complete is the lead information? Consider filled fields, data quality, enrichment status.
2. CLARITY SCORE: How clear and specific are the requirements/description?
3. ENGAGEMENT SCORE: How engaged is the lead? Consider interaction history, response time, activity.
4. INDUSTRY FIT SCORE: How well does the company's industry match technology/healthcare/real-estate/fintech verticals?
5. AUTHORITY SCORE: Is the contact a decision-maker (C-suite, Director, Owner) or influencer?
6. BUDGET CAPACITY SCORE: Based on employee count, revenue range, and funding — does this company have budget for technology investment?

Provide your analysis in this exact JSON format:
{{
    "completeness_score": <0-100>,
    "clarity_score": <0-100>,
    "engagement_score": <0-100>,
    "industry_fit_score": <0-100>,
    "authority_score": <0-100>,
    "budget_capacity_score": <0-100>,
    "probability_score": <0-100>,
    "summary": "<2-3 sentence B2B sales analysis>",
    "recommendation": "<specific actionable recommendation for the salesperson>",
    "sales_play": "<one of: Immediate Demo, Discovery Call, Educational Nurture, Deep Qualification, Re-engagement Campaign, Trigger Event Monitoring, Park / Low Priority>"
}}
"""

RESEARCH_PROMPT = """Research this company based on the available information:
- Company Name: {company_name}
- Website: {website}
- Industry: {industry}
- Country: {country}

Provide a concise research summary (max 150 words) covering:
1. What this company likely does based on available data
2. Their potential size/scale
3. Key observations relevant to our sales approach
"""

DIGITAL_PRESENCE_PROMPT = """Analyze the digital presence for this company:
- Company: {company_name}
- Website: {website}

Based on the name and website, infer:
1. Likely tech stack (CMS, analytics, frameworks)
2. Social media presence expectations
3. SEO/Online visibility assessment

Keep response concise, max 100 words.
"""


class LlmService(models.Model):
    _name = 'llm.service'
    _description = 'LLM Scoring Service'

    def score_lead(self, lead, provider=None):
        provider = provider or self.env['llm.provider'].get_default_provider()
        if not provider:
            raise UserError(_('No LLM provider configured'))

        customer_research = self._gather_customer_research(lead)
        def _sf(obj, attr):
            try:
                f = obj._fields.get(attr)
                if f and f.type == 'many2one':
                    return getattr(obj, attr).name or ''
                return getattr(obj, attr) or ''
            except Exception:
                return ''
        prompt = SCORING_PROMPT.format(
            name=lead.name or '',
            company_name=lead.partner_name or '',
            email=lead.email_from or '',
            email_verified='Yes' if lead.x_email_verified else 'No',
            phone=lead.phone or '',
            website=lead.website or '',
            description=lead.description or '',
            enriched_industry=(lead.x_company_industry or _sf(lead, 'industry_id') or 'Unknown'),
            employee_count=lead.x_employee_count or 0,
            annual_revenue=(lead.x_annual_revenue or 'Unknown'),
            tech_stack=(lead.x_tech_stack or 'Unknown'),
            contact_name=(lead.contact_name or 'Unknown'),
            job_title=(lead.x_job_title or 'Unknown'),
            seniority=(lead.x_seniority or 'Unknown'),
            country=(lead.country_id.name or ''),
            emirate=(lead.x_emirate or 'Unknown'),
            territory=(lead.x_territory or 'International'),
            source=_sf(lead, 'source_id'),
            stage=_sf(lead, 'stage_id'),
            research_data=customer_research or 'No additional research data available',
        )

        result = provider._make_request(prompt)
        return self._parse_score_response(result, lead)

    def research_customer(self, lead, provider=None):
        provider = provider or self.env['llm.provider'].get_default_provider()
        if not provider:
            raise UserError(_('No LLM provider configured'))

        def _sf(obj, attr):
            try:
                f = obj._fields.get(attr)
                if f and f.type == 'many2one':
                    return getattr(obj, attr).name or ''
                return getattr(obj, attr) or ''
            except Exception:
                return ''
        prompt = RESEARCH_PROMPT.format(
            company_name=lead.partner_name or lead.name or '',
            website=lead.website or '',
            industry=_sf(lead, 'industry_id'),
            country=_sf(lead, 'country_id'),
        )

        return provider._make_request(prompt)

    def analyze_digital_presence(self, lead, provider=None):
        provider = provider or self.env['llm.provider'].get_default_provider()
        if not provider:
            raise UserError(_('No LLM provider configured'))

        prompt = DIGITAL_PRESENCE_PROMPT.format(
            company_name=lead.partner_name or lead.name or '',
            website=lead.website or '',
        )

        return provider._make_request(prompt)

    def _gather_customer_research(self, lead):
        parts = []
        if lead.website:
            parts.append('Website: %s' % lead.website)
        if lead.partner_name:
            parts.append('Company: %s' % lead.partner_name)

        web_research = self.env.get('web.research.service')
        if web_research and lead.partner_name:
            try:
                result = web_research.search_company_info(lead.partner_name, lead.website)
                if result.get('success'):
                    for r in result.get('results', []):
                        parts.append('Web Research: %s - %s' % (r.get('title', ''), r.get('snippet', '')))
            except Exception:
                pass

        return '\n'.join(parts) if parts else ''

    def _parse_score_response(self, response, lead):
        import re
        import json

        def _extract_json(text):
            candidates = []
            m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
            if m:
                candidates.append(m.group(1).strip())
            depth = 0
            start = -1
            for i, ch in enumerate(text):
                if ch == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        candidates.append(text[start:i+1])
                        start = -1
            return candidates

        candidates = _extract_json(response)
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                required = ['completeness_score', 'clarity_score', 'engagement_score', 'probability_score']
                if all(k in data for k in required):
                    sales_play = data.get('sales_play', '')
                    vals = {
                        'ai_completeness_score': min(max(int(data['completeness_score']), 0), 100),
                        'ai_clarity_score': min(max(int(data['clarity_score']), 0), 100),
                        'ai_engagement_score': min(max(int(data['engagement_score']), 0), 100),
                        'ai_probability_score': min(max(int(data['probability_score']), 0), 100),
                        'ai_analysis_summary': data.get('summary', ''),
                        'ai_enrichment_status': 'scored',
                        'ai_last_enrichment_date': fields.Datetime.now(),
                    }
                    if sales_play:
                        vals['x_sales_play'] = sales_play[:64]
                    lead.write(vals)
                    return True
            except (json.JSONDecodeError, ValueError, KeyError):
                continue

        _logger.warning('Failed to parse LLM score response from: %s...', response[:200])
        lead.write({
            'ai_enrichment_status': 'failed',
            'ai_last_enrichment_date': fields.Datetime.now(),
        })
        return False
