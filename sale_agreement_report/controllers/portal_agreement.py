# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request


class CustomerPortalAgreement(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id.commercial_partner_id
        count = request.env['sale.agreement'].sudo().search_count([
            ('partner_id', 'child_of', partner.id)
        ])
        values['agreement_count'] = count
        return values

    @http.route(['/my/agreements', '/my/agreements/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_agreements(self, page=1, sortby='year', **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id.commercial_partner_id
        Agreement = request.env['sale.agreement'].sudo()

        domain = [('partner_id', 'child_of', partner.id)]
        sortings = {
            'year': {'label': _('Year'), 'order': 'agreement_year desc, id desc'},
            'name': {'label': _('Reference'), 'order': 'name asc'},
        }
        sort_order = sortings[sortby]['order'] if sortby in sortings else sortings['year']['order']

        total = Agreement.search_count(domain)
        pager = portal_pager(
            url='/my/agreements',
            total=total,
            page=page,
            step=20,
            url_args={'sortby': sortby},
        )
        agreements = Agreement.search(domain, order=sort_order, limit=20, offset=pager['offset'])

        values.update({
            'agreements': agreements,
            'page_name': 'agreements',
            'pager': pager,
            'default_url': '/my/agreements',
            'sortings': sortings,
            'sortby': sortby,
        })
        return request.render('sale_agreement_report.portal_my_agreements', values)

    @http.route('/my/agreements/<int:agreement_id>', type='http', auth='user', website=True)
    def portal_agreement_detail(self, agreement_id, **kw):
        agreement = self._get_portal_agreement_or_403(agreement_id)
        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'agreement_detail',
            'agreement': agreement,
        })
        return request.render('sale_agreement_report.portal_agreement_detail', values)

    @http.route('/my/agreements/<int:agreement_id>/download', type='http', auth='user', website=True)
    def portal_agreement_download(self, agreement_id, **kw):
        agreement = self._get_portal_agreement_or_403(agreement_id)
        report = request.env.ref('sale_agreement_report.action_report_yearly_sale_agreement').sudo()
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            report.report_name,
            [agreement.id],
        )
        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', 'attachment; filename="%s.pdf"' % agreement.name),
            ],
        )

    @http.route('/my/agreements/<int:agreement_id>/upload', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_agreement_upload(self, agreement_id, **post):
        agreement = self._get_portal_agreement_or_403(agreement_id)
        doc_type = post.get('doc_type')
        upload = request.httprequest.files.get('document')

        if not upload:
            return request.redirect('/my/agreements/%s?error=no_file' % agreement.id)

        filename = upload.filename
        file_bytes = upload.read()

        try:
            if doc_type == 'license':
                agreement.sudo().action_replace_license(filename, file_bytes)
            elif doc_type == 'owner':
                agreement.sudo().action_replace_owner_document(filename, file_bytes)
            else:
                return request.redirect('/my/agreements/%s?error=bad_doc_type' % agreement.id)
        except ValidationError as ex:
            error_text = str(ex).lower()
            if '10 mb' in error_text:
                error_code = 'file_too_large'
            elif 'pdf' in error_text or 'jpg' in error_text or 'png' in error_text:
                error_code = 'invalid_file_type'
            else:
                error_code = 'validation_failed'
            return request.redirect('/my/agreements/%s?error=%s' % (agreement.id, error_code))

        return request.redirect('/my/agreements/%s?success=1' % agreement.id)

    def _get_portal_agreement_or_403(self, agreement_id):
        agreement = request.env['sale.agreement'].sudo().browse(agreement_id)
        if not agreement.exists():
            raise MissingError(_('Agreement not found.'))

        partner = request.env.user.partner_id.commercial_partner_id
        if agreement.partner_id.commercial_partner_id != partner:
            raise AccessError(_('You do not have access to this agreement.'))

        return agreement
