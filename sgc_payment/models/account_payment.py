from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    voucher_number = fields.Char(string='Voucher Number', readonly=True, copy=False)
    verification_status = fields.Selection([
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
    ], string='Verification Status', default='pending')
    verification_code = fields.Char(string='Verification Code', readonly=True, copy=False)
    verification_date = fields.Datetime(string='Verification Date', readonly=True)
    qr_verification_ids = fields.One2many(
        'payment.qr.verification', 'payment_id', string='QR Verifications'
    )
    approval_history_ids = fields.One2many(
        'payment.approval.history', 'payment_id', string='Approval History'
    )

    approval_state = fields.Selection(related='move_id.approval_state', store=True)
