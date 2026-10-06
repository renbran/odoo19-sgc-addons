from odoo import models, fields


class PaymentQrVerification(models.Model):
    _name = 'payment.qr.verification'
    _description = 'Payment QR Verification'
    _order = 'verification_date desc'

    verification_date = fields.Datetime(string='Verification Date', default=fields.Datetime.now, readonly=True)
    verification_code = fields.Char(string='Verification Code', required=True, readonly=True)
    payment_voucher_number = fields.Char(string='Voucher Number', readonly=True)
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)
    payment_partner_id = fields.Many2one('res.partner', string='Partner', readonly=True)
    payment_amount = fields.Monetary(string='Amount', currency_field='payment_currency_id', readonly=True)
    payment_currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    payment_verification_status = fields.Char(string='Payment Verification Status', readonly=True)
    verification_method = fields.Selection([
        ('qr_scan', 'QR Scan'),
        ('manual_entry', 'Manual Entry'),
    ], string='Method', default='qr_scan', required=True, readonly=True)
    verification_status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('invalid', 'Invalid'),
        ('expired', 'Expired'),
    ], string='Status', required=True, readonly=True)
    verifier_ip = fields.Char(string='Verifier IP', readonly=True)
    verifier_user_agent = fields.Text(string='User Agent', readonly=True)
    additional_data = fields.Text(string='Additional Data', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
