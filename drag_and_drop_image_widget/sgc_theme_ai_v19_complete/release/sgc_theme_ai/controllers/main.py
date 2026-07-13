# -*- coding: utf-8 -*-
"""
SGC TECH AI Theme website controllers.

This module keeps the public website install-safe on clean Odoo 19 databases:
- `/home` renders the branded homepage template.
- post_init_hook points the default website homepage to `/home`.
- `/solutions` is a real landing page instead of a dead navigation link.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SGCWebsite(http.Controller):

    @http.route('/home', type='http', auth='public', website=True)
    def home(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_homepage', {})

    @http.route('/sgc/roi/calculate', type='jsonrpc', auth='public',
                methods=['POST'], csrf=False, website=True)
    def calculate_roi(self, **kwargs):
        """Server-side ROI calculation used by the public calculator."""
        employees = max(1, min(int(kwargs.get('employees', 10)), 10000))
        monthly_cost = max(0.0, min(float(kwargs.get('monthly_cost', 100000)), 1e9))
        industry = str(kwargs.get('industry', 'real_estate'))
        hours_per_week = max(1.0, min(float(kwargs.get('hours_per_week', 40)), 168))

        multipliers = {
            'real_estate': {'time': 0.55, 'error': 0.92, 'efficiency': 0.45, 'base_roi': 1.75},
            'trading': {'time': 0.48, 'error': 0.88, 'efficiency': 0.40, 'base_roi': 1.65},
            'manufacturing': {'time': 0.42, 'error': 0.85, 'efficiency': 0.38, 'base_roi': 1.55},
            'professional_services': {'time': 0.60, 'error': 0.90, 'efficiency': 0.50, 'base_roi': 1.85},
            'hospitality': {'time': 0.40, 'error': 0.82, 'efficiency': 0.35, 'base_roi': 1.50},
        }
        mult = multipliers.get(industry, multipliers['real_estate'])

        annual_cost = monthly_cost * 12
        labor_cost = annual_cost * 0.70
        total_hours_yr = employees * 52 * hours_per_week
        hourly_rate = labor_cost / total_hours_yr if total_hours_yr > 0 else 50

        saved_hours = total_hours_yr * mult['time'] * 0.35
        labor_savings = saved_hours * hourly_rate
        error_savings = annual_cost * 0.08 * mult['error']
        efficiency_gains = annual_cost * mult['efficiency'] * 0.25
        revenue_uplift = annual_cost * 0.15 * mult['base_roi']
        total_benefit = labor_savings + error_savings + efficiency_gains + revenue_uplift

        if employees <= 15:
            pkg_price, pkg_name = 25000, 'Starter'
        elif employees <= 50:
            pkg_price, pkg_name = 45000, 'Growth'
        else:
            pkg_price, pkg_name = 85000, 'Enterprise'

        total_investment = pkg_price * 1.15
        net_benefit = total_benefit - total_investment
        roi_pct_real = round((net_benefit / total_investment) * 100) if total_investment else 0
        roi_pct_display = max(150, roi_pct_real)
        payback_months = round(pkg_price / (total_benefit / 12)) if total_benefit > 0 else 99

        return {
            'roi': roi_pct_display,
            'roi_actual': roi_pct_real,
            'annual_savings': round(total_benefit),
            'labor_savings': round(labor_savings),
            'error_savings': round(error_savings),
            'efficiency_gains': round(efficiency_gains + revenue_uplift),
            'investment': pkg_price,
            'payback': payback_months,
            'saved_hours': round(saved_hours / 12),
            'net_benefit': round(net_benefit),
            'package': pkg_name,
            'currency': 'AED',
        }

    @http.route('/sgc/lead', type='jsonrpc', auth='public',
                methods=['POST'], csrf=True, website=True)
    def capture_lead(self, **kwargs):
        """Create CRM lead from website form submissions."""
        name = str(kwargs.get('name', ''))[:128].strip()
        email = str(kwargs.get('email', ''))[:254].strip()
        phone = str(kwargs.get('phone', ''))[:32].strip()
        company = str(kwargs.get('company', ''))[:128].strip()
        message = str(kwargs.get('message', ''))[:2000].strip()

        if not name or not email:
            return {'success': False, 'error': 'Name and email are required.'}

        try:
            desc_parts = [message]
            if kwargs.get('employees'):
                desc_parts.append(
                    f"\n\n--- ROI Calculator Data ---\n"
                    f"Employees: {int(kwargs.get('employees', 0))}\n"
                    f"Industry: {str(kwargs.get('industry', ''))[:64]}\n"
                    f"Monthly Costs (AED): {float(kwargs.get('monthly_cost', 0)):.2f}\n"
                    f"Projected ROI: {str(kwargs.get('roi_percent', ''))[:16]}%"
                )

            lead = request.env['crm.lead'].sudo().create({
                'name': f"Website Lead: {name}",
                'contact_name': name,
                'email_from': email,
                'phone': phone,
                'partner_name': company,
                'description': '\n'.join(desc_parts),
            })
            _logger.info('SGC Lead #%d created for %s', lead.id, email)
            return {'success': True, 'lead_id': lead.id}
        except Exception as exc:
            _logger.error('SGC lead creation error: %s', exc)
            return {'success': False, 'error': 'Submission failed. Please try again.'}

    @http.route('/pricing', type='http', auth='public', website=True)
    def pricing(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_pricing', {})

    @http.route('/about', type='http', auth='public', website=True)
    def about(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_about', {})

    @http.route(['/appointment', '/book-consultation', '/book'],
                type='http', auth='public', website=True)
    def appointment(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_appointment', {
            'package': kwargs.get('package', ''),
            'trial': kwargs.get('trial', ''),
        })

    @http.route('/success-stories', type='http', auth='public', website=True)
    def success_stories(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_success_stories', {})

    def _solution_context(self, key: str) -> dict:
        solutions = {
            'overview': {
                'title': 'Odoo ERP Solutions for UAE Growth Teams',
                'subtitle': 'Explore SGC TECH AI deployments for real estate, trading, manufacturing, services, HR, and analytics teams.',
                'kpi_1': '6 solution tracks',
                'kpi_2': '14-day go-live model',
                'kpi_3': '150% ROI floor',
                'cta_label': 'Book Solution Discovery',
                'slug': 'solutions',
            },
            'real-estate': {
                'title': 'Real Estate ERP for UAE Agencies',
                'subtitle': 'Automate rentals, sales, commissions, and owner portals in 14 days.',
                'kpi_1': '60 hrs/mo saved',
                'kpi_2': '90% error reduction',
                'kpi_3': '30-day free trial',
                'cta_label': 'Start Real Estate Consultation',
                'slug': 'real-estate',
            },
            'trading': {
                'title': 'Trading & Distribution ERP',
                'subtitle': 'Control procurement, inventory, sales, and margins in one unified dashboard.',
                'kpi_1': '35% faster fulfillment',
                'kpi_2': 'Real-time stock visibility',
                'kpi_3': '14-day go-live',
                'cta_label': 'Book Trading Consultation',
                'slug': 'trading',
            },
            'manufacturing': {
                'title': 'Manufacturing ERP',
                'subtitle': 'Optimize MRP, production planning, quality, and cost controls across plants.',
                'kpi_1': '22% less production delay',
                'kpi_2': 'Live OEE monitoring',
                'kpi_3': 'UAE compliance ready',
                'cta_label': 'Book Manufacturing Consultation',
                'slug': 'manufacturing',
            },
            'professional-services': {
                'title': 'Professional Services ERP',
                'subtitle': 'Track billable hours, delivery margins, and project profitability without spreadsheets.',
                'kpi_1': '18% better utilization',
                'kpi_2': 'Faster invoicing cycles',
                'kpi_3': '150% ROI floor',
                'cta_label': 'Book Services Consultation',
                'slug': 'professional-services',
            },
            'hr-payroll': {
                'title': 'HR & Payroll ERP for UAE',
                'subtitle': 'Unify attendance, leaves, payroll, and employee self-service in one secure platform.',
                'kpi_1': 'Payroll in minutes',
                'kpi_2': 'Reduced HR admin load',
                'kpi_3': 'Audit-ready records',
                'cta_label': 'Book HR & Payroll Consultation',
                'slug': 'hr-payroll',
            },
            'ai-analytics': {
                'title': 'AI Analytics & Executive Dashboards',
                'subtitle': 'Turn live business data into forecasting, risk alerts, and growth insights.',
                'kpi_1': 'Decision speed up 2x',
                'kpi_2': 'Live KPI command center',
                'kpi_3': 'Actionable AI insights',
                'cta_label': 'Book AI Analytics Consultation',
                'slug': 'ai-analytics',
            },
        }
        return solutions.get(key, solutions['real-estate'])

    @http.route('/solutions', type='http', auth='public', website=True)
    def solutions(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('overview'))

    @http.route(['/solutions/real-estate', '/real-estate-module'],
                type='http', auth='public', website=True)
    def real_estate(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_real_estate', {})

    @http.route('/solutions/trading', type='http', auth='public', website=True)
    def solution_trading(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('trading'))

    @http.route('/solutions/manufacturing', type='http', auth='public', website=True)
    def solution_manufacturing(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('manufacturing'))

    @http.route('/solutions/professional-services', type='http', auth='public', website=True)
    def solution_professional_services(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('professional-services'))

    @http.route('/solutions/hr-payroll', type='http', auth='public', website=True)
    def solution_hr_payroll(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('hr-payroll'))

    @http.route('/solutions/ai-analytics', type='http', auth='public', website=True)
    def solution_ai_analytics(self, **kwargs):
        return request.render('sgc_theme_ai.sgc_solution_generic', self._solution_context('ai-analytics'))
