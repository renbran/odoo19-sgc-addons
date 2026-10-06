# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # ============================================================================
    # PAYMENT VERIFICATION AND WORKFLOW SETTINGS
    # ============================================================================
    
    enable_payment_verification = fields.Boolean(
        string="Enable Payment Verification",
        default=True,
        help="Globally enable payment verification via QR codes"
    )
    
    default_journal_for_payments = fields.Many2one(
        'account.journal',
        string="Default Journal for Payments",
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="Default journal for new payments"
    )
    
    # OSUS Branding and Payment Settings
    use_osus_branding = fields.Boolean(
        string='Use OSUS Branding',
        default=True,
        help="Apply OSUS brand guidelines to payment vouchers"
    )
    
    auto_post_approved_payments = fields.Boolean(
        string='Auto-Post Approved Payments',
        default=False,
        help="Automatically post payments when approved"
    )
    
    max_approval_amount = fields.Monetary(
        string='Maximum Approval Amount',
        currency_field='currency_id',
        default=10000.0,
        help="Maximum amount that regular users can approve"
    )
    
    send_approval_notifications = fields.Boolean(
        string='Send Approval Notifications',
        default=True,
        help="Send email notifications for approval requests"
    )
    
    require_remarks_for_large_payments = fields.Boolean(
        string='Require Remarks for Large Payments',
        default=True,
        help="Require remarks for payments above the maximum approval amount"
    )
    
    voucher_footer_message = fields.Text(
        string='Voucher Footer Message',
        default='Thank you for your business with OSUS Properties',
        help="Custom footer message for payment vouchers"
    )
    
    voucher_terms = fields.Text(
        string='Voucher Terms',
        default='This is a computer-generated document. No physical signature required for system verification.',
        help="Terms and conditions text for payment vouchers"
    )
    
    # Workflow Settings
    enable_four_stage_approval = fields.Boolean(
        string='Enable 4-Stage Approval',
        default=True,
        help="Enable the full 4-stage approval workflow for vendor payments"
    )
    
    authorization_threshold = fields.Monetary(
        string='Authorization Threshold',
        currency_field='currency_id',
        default=5000.0,
        help="Amount below which authorization stage is skipped"
    )
    
    # QR Code Settings
    enable_qr_codes = fields.Boolean(
        string='Enable QR Codes',
        default=True,
        help="Generate QR codes for payment vouchers"
    )
    
    qr_code_verification_url = fields.Char(
        string='QR Verification URL',
        help="Custom URL for QR code verification portal"
    )
    
    @api.model
    def get_payment_voucher_settings(self):
        """Get comprehensive payment voucher settings for current company"""
        company = self.env.company
        return {
            'enable_payment_verification': company.enable_payment_verification,
            'use_osus_branding': company.use_osus_branding,
            'auto_post_approved_payments': company.auto_post_approved_payments,
            'max_approval_amount': company.max_approval_amount,
            'send_approval_notifications': company.send_approval_notifications,
            'require_remarks_for_large_payments': company.require_remarks_for_large_payments,
            'voucher_footer_message': company.voucher_footer_message,
            'voucher_terms': company.voucher_terms,
            'enable_four_stage_approval': company.enable_four_stage_approval,
            'authorization_threshold': company.authorization_threshold,
            'enable_qr_codes': company.enable_qr_codes,
            'qr_code_verification_url': company.qr_code_verification_url,
        }
