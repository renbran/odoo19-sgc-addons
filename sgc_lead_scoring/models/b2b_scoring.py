import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

SALES_PLAY_MATRIX = [
    {
        'ai_min': 70, 'bant_min': 70, 'industry': 'high',
        'play': 'Immediate Demo',
        'desc': 'Hot qualified lead. Schedule personalized demo within 24h. Send case studies from similar verticals. Involve senior sales.',
    },
    {
        'ai_min': 50, 'bant_min': 50, 'industry': 'high',
        'play': 'Discovery Call',
        'desc': 'Good fit, needs qualification. Schedule discovery call. Understand budget timeline and decision process.',
    },
    {
        'ai_min': 70, 'bant_min': 50, 'industry': 'medium',
        'play': 'Educational Nurture',
        'desc': 'Strong lead but needs education on value proposition. Send industry-specific content and case studies before call.',
    },
    {
        'ai_min': 50, 'bant_min': 70, 'industry': 'medium',
        'play': 'Deep Qualification',
        'desc': 'Strong form data but AI sees gaps. Re-qualify with targeted questions about requirements and timeline.',
    },
    {
        'ai_min': 30, 'bant_min': 30, 'industry': 'high',
        'play': 'Re-engagement Campaign',
        'desc': 'Good industry fit but low engagement. Run targeted email sequence with relevant content. Attempt re-contact.',
    },
    {
        'ai_min': 0, 'bant_min': 0, 'industry': 'high',
        'play': 'Long-term Nurture',
        'desc': 'Right industry but insufficient data. Add to nurture campaign. Enrich data before scoring.',
    },
    {
        'ai_min': 70, 'bant_min': 0,
        'play': 'Trigger Event Monitoring',
        'desc': 'High AI score but low BANT — likely early stage. Monitor for trigger events (funding, leadership change, growth).',
    },
    {
        'ai_min': 0, 'bant_min': 0, 'industry': 'low',
        'play': 'Park / Low Priority',
        'desc': 'Industry mismatch. Do not allocate sales time. Add to low-priority nurture if potential exists.',
    },
]

INDUSTRY_SIGNAL_KEYWORDS = {
    'technology': ['software', 'saas', 'cloud', 'it ', 'technology', 'digital', 'tech', 'computer', 'platform'],
    'healthcare': ['healthcare', 'medical', 'clinic', 'hospital', 'health', 'pharma', 'wellness', 'dental'],
    'real_estate': ['real estate', 'property', 'brokerage', 'reality', 'construction', 'developer', 'facilities'],
    'finance': ['finance', 'banking', 'insurance', 'investment', 'fintech', 'accounting', 'financial'],
    'education': ['education', 'school', 'training', 'academy', 'institute', 'learning', 'university'],
    'manufacturing': ['manufacturing', 'factory', 'production', 'industrial', 'logistics', 'supply chain'],
    'retail': ['retail', 'ecommerce', 'wholesale', 'distribution', 'store', 'trading'],
    'hospitality': ['hotel', 'hospitality', 'travel', 'tourism', 'restaurant', 'catering'],
}


class B2BScoringEngine(models.AbstractModel):
    _name = 'b2b.scoring.engine'
    _description = 'B2B Lead Scoring Engine'

    def _get_target_industries(self):
        config = self.env['ir.config_parameter'].sudo()
        raw = config.get_param('sgc_lead_scoring.target_industries', 'technology,healthcare,real_estate,finance')
        return [i.strip() for i in raw.split(',') if i.strip()]

    def _get_ideal_company_size_min(self):
        config = self.env['ir.config_parameter'].sudo()
        return int(config.get_param('sgc_lead_scoring.ideal_company_size_min', '10'))

    def _get_ideal_company_size_max(self):
        config = self.env['ir.config_parameter'].sudo()
        return int(config.get_param('sgc_lead_scoring.ideal_company_size_max', '500'))

    def _compute_industry_fit(self, lead):
        target = self._get_target_industries()
        industry = (lead.x_company_industry or '').lower()
        if not industry:
            description = (lead.description or '').lower()
            partner = (lead.partner_name or '').lower()
            for sector, keywords in INDUSTRY_SIGNAL_KEYWORDS.items():
                for kw in keywords:
                    if kw in industry or kw in description or kw in partner:
                        if sector in target:
                            return 'high', sector
                        return 'low', sector

        for sector in target:
            keywords = INDUSTRY_SIGNAL_KEYWORDS.get(sector, [sector])
            for kw in keywords:
                if kw in industry:
                    return 'high', sector

        return 'medium', 'general'

    def _compute_authority_level(self, lead):
        seniority = lead.x_seniority or ''
        title = (lead.x_job_title or '').lower()
        contact = (lead.contact_name or '').lower()

        c_level = ['owner', 'c_suite', 'partner', 'founder', 'ceo', 'cto',
                   'cfo', 'coo', 'cmo', 'cio', 'president', 'vp']
        director = ['director', 'head of', 'senior manager']
        manager = ['manager', 'team lead', 'supervisor']

        s = seniority.lower()
        if s == 'owner' or s == 'c_suite':
            return 'c_suite'
        if s == 'vp' or s == 'director':
            return 'director'
        if s == 'manager':
            return 'manager'

        for keyword in c_level:
            if keyword in title or keyword in contact:
                return 'c_suite'
        for keyword in director:
            if keyword in title:
                return 'director'
        for keyword in manager:
            if keyword in title:
                return 'manager'

        if title or contact:
            return 'ic'
        return 'unknown'

    def _compute_company_size_score(self, lead):
        emp = lead.x_employee_count or 0
        if emp <= 0:
            return 50
        min_size = self._get_ideal_company_size_min()
        max_size = self._get_ideal_company_size_max()
        if min_size <= emp <= max_size:
            return 100
        if emp < min_size:
            ratio = emp / max(min_size, 1)
            return int(ratio * 60)
        ratio = max_size / max(emp, 1)
        return int(ratio * 60)

    def _compute_budget_capacity_score(self, lead):
        revenue = (lead.x_annual_revenue or '').lower()
        emp = lead.x_employee_count or 0
        funding = lead.x_funding_total or 0

        signals = 0
        if revenue:
            for pattern in ['$10m', '$50m', '$100m', '$1b', 'million', 'billion']:
                if pattern in revenue:
                    signals += 2
                    break
            for pattern in ['$1m', '$5m', '$2m', '$3m']:
                if pattern in revenue:
                    signals += 1
                    break

        if emp >= 50:
            signals += 2
        elif emp >= 10:
            signals += 1

        if funding > 0:
            signals += 2
            if funding >= 1000000:
                signals += 1

        return min(signals * 20, 100)

    def _compute_tech_fit_score(self, lead):
        tech = (lead.x_tech_stack or '')
        if not tech:
            return 50

        desc = (lead.description or '').lower()
        tech_lower = tech.lower()

        modern_signals = ['react', 'cloud', 'aws', 'azure', 'api', 'digital',
                          'analytics', 'crm', 'erp', 'saas', 'mobile']
        found = sum(1 for s in modern_signals if s in tech_lower or s in desc)
        return min(found * 15 + 40, 100)

    def _compute_engagement_depth(self, lead):
        score = 50
        if lead.email_from and '@' in lead.email_from:
            score += 10
        if lead.phone:
            score += 10
        if lead.website:
            score += 5
        if lead.x_email_verified:
            score += 10
        if lead.description and len(lead.description) > 100:
            score += 10
        if lead.x_last_contact_date:
            score += 5
        return min(score, 100)

    def _determine_sales_play(self, ai_score, bant_total, industry_fit):
        for play in SALES_PLAY_MATRIX:
            ai_ok = ai_score >= play.get('ai_min', 0)
            bant_ok = bant_total >= play.get('bant_min', 0)
            ind_ok = play.get('industry', '') in ('', industry_fit)
            if ai_ok and bant_ok and ind_ok:
                return play['play']
        return 'Standard Follow-up'

    def compute_all(self, lead):
        industry_fit, industry_sector = self._compute_industry_fit(lead)
        authority = self._compute_authority_level(lead)
        company_size = self._compute_company_size_score(lead)
        budget_capacity = self._compute_budget_capacity_score(lead)
        tech_fit = self._compute_tech_fit_score(lead)
        engagement = self._compute_engagement_depth(lead)

        bant_service = self.env.get('lead.scoring.report')
        bant_total = 50
        if bant_service:
            bant = bant_service._compute_bant_score(lead)
            bant_total = bant.get('total', 50)

        ai_score = lead.ai_probability_score or 50
        sales_play = self._determine_sales_play(ai_score, bant_total, industry_fit)

        lead.write({
            'x_industry_fit': industry_fit,
            'x_contact_authority': authority,
            'x_sales_play': sales_play,
        })

        return {
            'industry_fit': industry_fit,
            'industry_sector': industry_sector,
            'authority': authority,
            'company_size_score': company_size,
            'budget_capacity_score': budget_capacity,
            'tech_fit_score': tech_fit,
            'engagement_depth': engagement,
            'sales_play': sales_play,
        }
