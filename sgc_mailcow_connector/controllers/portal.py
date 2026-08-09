from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal
import binascii
import json
from odoo.http import Response

class SgcEmployeeDocumentPortal(CustomerPortal):
    def _document_get_sudo(self, doc_id, access_token=None):
        return self._document_check_access('sgc.employee.document', doc_id, access_token)

    @http.route(['/my/employee-documents/<int:doc_id>'], type='http', auth='public', website=True)
    def portal_employee_document(self, doc_id, access_token=None, **kw):
        try:
            doc_sudo = self._document_get_sudo(doc_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(doc_sudo, access_token, {'doc': doc_sudo, 'page_name': 'employee_document'}, 'my_employee_documents_history', False)
        return request.render('sgc_mailcow_connector.portal_employee_document', values)

    @http.route(['/my/employee-documents/<int:doc_id>/sign'], type='jsonrpc', auth='public', website=True)
    def portal_employee_document_sign(self, doc_id, access_token=None, name=None, signature=None, **kw):
        access_token = access_token or request.httprequest.args.get('access_token')
        try:
            doc_sudo = self._document_get_sudo(doc_id, access_token)
        except (AccessError, MissingError):
            return {'error': _('Invalid document.')}
        if not doc_sudo._has_to_be_signed():
            return {'error': _('The document is not in a state requiring signature.')}
        if not signature:
            return {'error': _('Signature is missing.')}
        try:
            doc_sudo.write({
                'signed_by': name,
                'signed_on': fields.Datetime.now(),
                'signature': signature,
                'state': 'signed',
            })
            request.env.cr.flush()
        except (TypeError, binascii.Error):
            return {'error': _('Invalid signature data.')}
        # Re-render PDF with signature
        doc_sudo.action_store_pdf()
        # Message post: mirror sale's logic
        pdf = request.env['ir.actions.report'].sudo().with_context(sgc_include_signature=True)._render_qweb_pdf(doc_sudo._REPORT_XMLIDS[doc_sudo.doc_type], [doc_sudo.id])[0]
        doc_sudo.message_post(
            attachments=[(f'{doc_sudo.name}.pdf', pdf)],
            author_id=doc_sudo.employee_id.user_id.partner_id.id if not request.env.user._is_public() else request.env.user.partner_id.id,
            body=_('Document signed by %s', name),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        return {
            'force_refresh': True,
            'redirect_url': doc_sudo.get_portal_url(query_string='&message=sign_ok'),
        }
