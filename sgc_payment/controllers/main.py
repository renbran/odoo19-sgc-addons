from odoo import http
from odoo.http import request


class PaymentVerificationController(http.Controller):

    @http.route('/payment/verify/<string:code>', type='http', auth='public', sitemap=False)
    def verify_payment(self, code):
        verification = request.env['payment.qr.verification'].sudo().search([
            ('verification_code', '=', code)
        ], limit=1)
        if verification:
            verification.write({
                'verification_status': 'success',
            })
            return request.render('sgc_payment.verification_success', {
                'payment': verification.payment_id,
            })
        return request.not_found()

    @http.route('/payment/verify/submit', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def submit_verification(self, **kwargs):
        code = kwargs.get('code')
        if not code:
            return {'success': False, 'error': 'No code provided'}
        verification = request.env['payment.qr.verification'].sudo().create({
            'verification_code': code,
            'verification_method': 'manual_entry',
            'verification_status': 'success',
            'verifier_ip': request.httprequest.remote_addr,
            'verifier_user_agent': request.httprequest.user_agent.string if request.httprequest.user_agent else '',
        })
        return {'success': True, 'verification_id': verification.id}
