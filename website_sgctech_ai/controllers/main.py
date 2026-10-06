# -*- coding: utf-8 -*-
"""
SGC TECH AI — Website Controller
Theme-specific JSON endpoints (homepage stats, etc.).
Does NOT inherit from the base Website controller to avoid hijacking
Odoo's own route handlers (/shop, /page, /blog …).
"""
from odoo import http
from odoo.http import request, Response
import json
import re


class SGCTechWebsite(http.Controller):
    """Standalone controller for SGC TECH AI theme endpoints.

    The main homepage is served automatically by the ``website.page`` record
    registered in ``views/homepage.xml`` (URL: ``/sgctech-home``).  This
    controller adds supplementary JSON endpoints used by the front-end JS.
    """

    # ------------------------------------------------------------------ #
    #  Public JSON endpoint — live stats for animated counters            #
    # ------------------------------------------------------------------ #
    @http.route('/sgctech/stats', type='json', auth='public',
                methods=['POST'], website=True)
    def sgctech_stats(self, **kwargs):
        """Return key business stats for the counter animation.

        In a production setup these values could be pulled from sale.order,
        product.template, or a dedicated stats model.  For now they are
        static; replace with real queries as needed.

        Returns:
            dict: keys matching ``data-count`` targets in homepage.xml
        """
        return {
            'packages_delivered': 200,
            'avg_deploy_days':    14,
            'client_rating':      4.9,
            'instant_downloads':  100,
        }

    @http.route('/tools/odoo-roi-calculator', type='http', auth='public', website=True)
    def odoo_roi_calculator_page(self, **kwargs):
        return request.render('website_sgctech_ai.sgc_odoo_roi_calculator')

    @http.route('/tools/odoo-roi-calculator/calculate', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def odoo_roi_calculate(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or kwargs
        try:
            annual_revenue = float(payload.get('annual_revenue') or 0)
            employees = int(payload.get('employees') or 0)
            pain_points = payload.get('pain_points') or []
            if isinstance(pain_points, str):
                pain_points = [p.strip() for p in pain_points.split(',') if p.strip()]
        except (ValueError, TypeError):
            return self._json({'success': False, 'error': 'Invalid input values.'}, status=400)

        if annual_revenue <= 0 or employees <= 0:
            return self._json({'success': False, 'error': 'Annual revenue and employees must be greater than zero.'}, status=400)

        result = self._build_roi_result(annual_revenue, employees, pain_points)
        return self._json({'success': True, 'result': result})

    @http.route('/tools/odoo-roi-calculator/lead', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def odoo_roi_capture_lead(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or kwargs
        name = (payload.get('name') or '').strip()
        company = (payload.get('company') or '').strip()
        email = (payload.get('email') or '').strip().lower()

        if not name or not company or not email:
            return self._json({'success': False, 'error': 'Name, company, and email are required.'}, status=400)

        if not self._is_company_email(email):
            return self._json({'success': False, 'error': 'Please use your company email.'}, status=400)

        try:
            annual_revenue = float(payload.get('annual_revenue') or 0)
            employees = int(payload.get('employees') or 0)
            pain_points = payload.get('pain_points') or []
            if isinstance(pain_points, str):
                pain_points = [p.strip() for p in pain_points.split(',') if p.strip()]
        except (ValueError, TypeError):
            return self._json({'success': False, 'error': 'Invalid business inputs.'}, status=400)

        result = self._build_roi_result(annual_revenue, employees, pain_points)

        source = request.env.ref('website_sgctech_ai.crm_source_roi_calculator', raise_if_not_found=False)
        campaign = request.env.ref('website_sgctech_ai.campaign_roi_calculator', raise_if_not_found=False)
        request.env['crm.lead'].sudo().create({
            'name': f'ROI Calculator: {company}',
            'partner_name': company,
            'contact_name': name,
            'email_from': email,
            'type': 'lead',
            'source_id': source.id if source else False,
            'campaign_id': campaign.id if campaign else False,
            'description': (
                f'Odoo ROI Calculator submission\\n'
                f'Annual Revenue: {annual_revenue}\\n'
                f'Employees: {employees}\\n'
                f'Pain Points: {", ".join(pain_points) if pain_points else "None"}\\n'
                f'Estimated ROI Year 1: {result["roi_year_1_percent"]}%\\n'
                f'Estimated Payback (months): {result["payback_months"]}'
            ),
        })

        return self._json({
            'success': True,
            'message': 'Your ROI estimate has been captured. Our team will email your full report.',
            'result': result,
        })

    def _build_roi_result(self, annual_revenue, employees, pain_points):
        pain_count = len(pain_points)
        savings_rate = min(0.12, 0.02 + (pain_count * 0.007) + min(employees / 1000.0, 0.01))
        annual_savings = round(annual_revenue * savings_rate, 2)

        implementation_cost = round(15000 + (employees * 250) + (pain_count * 1200), 2)
        monthly_license = round(max(750, employees * 45), 2)
        year1_cost = round(implementation_cost + (monthly_license * 12), 2)
        year2plus_cost = round(monthly_license * 12, 2)

        year1_net = round(annual_savings - year1_cost, 2)
        roi_year_1_percent = round((year1_net / year1_cost) * 100, 2) if year1_cost else 0.0
        payback_months = round(implementation_cost / max((annual_savings / 12.0), 1), 1)
        three_year_benefit = round((annual_savings * 3) - (implementation_cost + (monthly_license * 36)), 2)

        return {
            'annual_savings': annual_savings,
            'implementation_cost': implementation_cost,
            'monthly_license': monthly_license,
            'year_1_total_cost': year1_cost,
            'year_2_plus_annual_cost': year2plus_cost,
            'year_1_net_benefit': year1_net,
            'roi_year_1_percent': roi_year_1_percent,
            'payback_months': payback_months,
            'three_year_net_benefit': three_year_benefit,
        }

    def _is_company_email(self, email):
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return False
        domain = email.split('@', 1)[1].lower()
        free_domains = {
            'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com',
            'aol.com', 'icloud.com', 'mail.com', 'protonmail.com'
        }
        return domain not in free_domains

    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type='application/json; charset=utf-8',
        )
