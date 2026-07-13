# models/account_journal.py
from odoo import models, fields, api, _

class AccountJournal(models.Model):
    _inherit = 'account.journal'
    
    enable_payment_verification = fields.Boolean(
        string="Enable Payment Verification",
        default=True,
        help="Enable QR verification for payments in this journal"
    )
    
    payment_approval_required = fields.Boolean(
        string='Require Payment Approval',
        default=True,
        help="Require approval workflow for payments in this journal"
    )


