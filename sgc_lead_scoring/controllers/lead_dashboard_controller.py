from odoo import http
from odoo.http import request


class LeadScoringDashboardController(http.Controller):

    @http.route('/ai/lead-scoring-dashboard', type='http', auth='user')
    def lead_scoring_dashboard(self):
        dashboard = request.env['lead.scoring.dashboard']
        html = dashboard.generate_dashboard()
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
        ])
