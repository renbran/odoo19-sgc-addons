# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class ConstructionPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'construction_project_count' in counters:
            partner = request.env.user.partner_id
            domain = self._get_portal_project_domain(partner)
            values['construction_project_count'] = request.env['construction.project'].sudo().search_count(domain)
        return values

    def _get_portal_project_domain(self, partner):
        return [
            ('client_id', 'child_of', partner.commercial_partner_id.id),
            ('state', 'not in', ['cancelled']),
        ]

    @http.route(['/my/construction-projects', '/my/construction-projects/page/<int:page>'],
                type='http', auth='user', website=True)
    def portal_construction_projects(self, page=1, **kw):
        partner = request.env.user.partner_id
        domain = self._get_portal_project_domain(partner)
        Project = request.env['construction.project'].sudo()
        total = Project.search_count(domain)
        pager = portal_pager(
            url='/my/construction-projects',
            total=total,
            page=page,
            step=10,
        )
        projects = Project.search(domain, limit=10, offset=pager['offset'],
                                  order='start_date desc, id desc')
        return request.render('sgc_construction_management.portal_my_construction_projects', {
            'projects': projects,
            'pager': pager,
            'page_name': 'construction_project',
        })

    @http.route('/my/construction-projects/<int:project_id>', type='http', auth='user', website=True)
    def portal_construction_project_detail(self, project_id, **kw):
        partner = request.env.user.partner_id
        domain = self._get_portal_project_domain(partner) + [('id', '=', project_id)]
        project = request.env['construction.project'].sudo().search(domain, limit=1)
        if not project:
            return request.not_found()
        wbs_phases = request.env['construction.wbs'].sudo().search(
            [('project_id', '=', project.id)], order='sequence, id')
        billings = request.env['construction.ra.billing'].sudo().search(
            [('project_id', '=', project.id),
             ('state', 'not in', ['draft'])],
            order='billing_date desc', limit=10)
        photos = request.env['construction.project.photo'].sudo().search(
            [('project_id', '=', project.id)],
            order='date desc, id desc', limit=12)
        return request.render('sgc_construction_management.portal_construction_project_detail', {
            'project': project,
            'wbs_phases': wbs_phases,
            'billings': billings,
            'photos': photos,
            'page_name': 'construction_project',
        })
