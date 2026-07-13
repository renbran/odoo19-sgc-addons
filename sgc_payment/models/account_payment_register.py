# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # Enhanced fields for payment voucher workflow
    remarks = fields.Text(
        string='Payment Remarks',
        help="Additional remarks for the payment voucher"
    )
    
    qr_in_report = fields.Boolean(
        string='Include QR Code in Report',
        default=False,
        help="Include QR code in the payment voucher report"
    )

    def _create_payment_vals_from_wizard(self, batch_result):
        """Override to include remarks and QR settings in payment creation and enforce workflow"""
        payment_vals = super()._create_payment_vals_from_wizard(batch_result)
        
        # Add custom fields to payment values
        if self.remarks:
            payment_vals['remarks'] = self.remarks
        
        # ENFORCE WORKFLOW: All payments start in draft state for approval workflow
        payment_vals.update({
            'approval_state': 'draft',  # Start in draft for workflow
        })
            
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        """Override to include remarks for batch payments"""
        payment_vals = super()._create_payment_vals_from_batch(batch_result)
        
        # Add custom fields to payment values
        if self.remarks:
            payment_vals['remarks'] = self.remarks
            
        return payment_vals

    def _post_payments(self, to_process, edit_mode=False):
        """Override to prevent immediate posting - enforce workflow"""
        # Skip posting - let workflow handle it
        return to_process