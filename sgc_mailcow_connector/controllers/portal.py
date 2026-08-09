from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError
import binascii


class SgcEmployeeDocumentPortal(CustomerPortal):

    def _document_get_sudo(self, doc_id, access_token=None):
        """ Get the document record sudoed, checking access rights """
        return self._document_check_access('sgc.employee.document', doc_id, access_token=access_token)

    @http.route(['/my/employee-documents/<int:doc_id>'], type='http', auth="public", website=True)
    def portal_employee_document(self, doc_id, access_token=None, **kw):
        try:
            doc_sudo = self._document_get_sudo(doc_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        values = self._get_page_view_values(doc_sudo, access_token, {'doc': doc_sudo}, 'my_employee_documents_history', False)
        return request.render('sgc_mailcow_connector.portal_employee_document', values)

    @http.route(['/my/employee-documents/<int:doc_id>/sign'], type='jsonrpc', auth="public", website=True)
    def portal_employee_document_sign(self, doc_id, access_token=None, name=None, signature=None, **kw):
        """ Handle the signature submission from the portal signature form """
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

        # Re-render and attach the signed PDF
        doc_sudo.action_store_pdf()
        
        # Get report reference safely for PDF generation
        report_xmlid = doc_sudo._REPORT_XMLIDS.get(doc_sudo.doc_type)
        if not report_xmlid:
            raise ValueError(_("No report configured for document type: %s") % doc_sudo.doc_type)
        doc_sudo.message_post(
            pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                report_xmlid, [doc_sudo.id])[0]
            attachments=[('%s.pdf' % doc_sudo.name, pdf)],
            body=_('Document signed by %s', name),
            subtype_xmlid='mail.mt_comment',
        )

        return {
            'force_refresh': True,
            'redirect_url': doc_sudo.get_portal_url(query_string='&message=sign_ok'),
        }