# -*- coding: utf-8 -*-

from odoo import http, fields, _
from odoo.http import request
import logging
import datetime

_logger = logging.getLogger(__name__)


class PaymentVerificationControllerSimple(http.Controller):
    """Simplified payment verification controller for debugging"""

    @http.route('/payment/verify/simple/<string:access_token>', type='http', auth='public', website=True, csrf=False)
    def verify_payment_simple(self, access_token, **kwargs):
        """Simplified payment verification page to debug internal server error"""
        try:
            _logger.info("Simple verification attempt for token: %s", access_token)
            
            # Find payment by access token
            payment = request.env['account.payment'].sudo().search([
                ('access_token', '=', access_token)
            ], limit=1)
            
            if not payment:
                return """
                <html>
                <body>
                    <h1>Payment Not Found</h1>
                    <p>The payment with access token %s was not found.</p>
                    <p><a href="/">Back to Home</a></p>
                </body>
                </html>
                """ % access_token
            
            # Simple HTML response without complex templates
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Payment Verification - {payment.voucher_number or payment.name}</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                    .header {{ background: #28a745; color: white; padding: 20px; border-radius: 6px; margin-bottom: 20px; }}
                    .verification-info {{ background: #f8f9fa; padding: 15px; border-left: 4px solid #28a745; margin: 20px 0; }}
                    .payment-details {{ background: #ffffff; border: 1px solid #e9ecef; border-radius: 6px; padding: 20px; }}
                    .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f1f1f1; }}
                    .detail-label {{ font-weight: bold; color: #495057; }}
                    .detail-value {{ color: #6c757d; }}
                    .status-badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; }}
                    .status-success {{ background: #d4edda; color: #155724; }}
                    .status-warning {{ background: #fff3cd; color: #856404; }}
                    .status-info {{ background: #d1ecf1; color: #0c5460; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>✓ Payment Verification Successful</h1>
                        <p>The payment details have been verified and are authentic.</p>
                    </div>
                    
                    <div class="verification-info">
                        <strong>Verification Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                        <strong>Verification Code:</strong> {access_token[:8].upper()}...
                    </div>
                    
                    <div class="payment-details">
                        <h3>Payment Details</h3>
                        
                        <div class="detail-row">
                            <span class="detail-label">Payment Number:</span>
                            <span class="detail-value">{payment.voucher_number or payment.name}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Partner:</span>
                            <span class="detail-value">{payment.partner_id.name or 'N/A'}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Amount:</span>
                            <span class="detail-value">{payment.currency_id.symbol or ''} {payment.amount:,.2f}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Date:</span>
                            <span class="detail-value">{payment.date.strftime('%Y-%m-%d') if payment.date else 'N/A'}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Type:</span>
                            <span class="detail-value">{'Money Received' if payment.payment_type == 'inbound' else 'Money Sent'}</span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Status:</span>
                            <span class="detail-value">
                                <span class="status-badge status-{'success' if payment.approval_state == 'posted' else 'info'}">
                                    {payment.approval_state.replace('_', ' ').title() if payment.approval_state else 'Draft'}
                                </span>
                            </span>
                        </div>
                        
                        <div class="detail-row">
                            <span class="detail-label">Company:</span>
                            <span class="detail-value">{payment.company_id.name}</span>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin-top: 30px; color: #6c757d;">
                        <p><small>This payment has been verified through secure QR code authentication.</small></p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html_content
            
        except Exception as e:
            _logger.error("Error in simple verification for token %s: %s", access_token, str(e))
            return f"""
            <html>
            <body>
                <h1>Verification Error</h1>
                <p>An error occurred while verifying the payment: {str(e)}</p>
                <p>Access Token: {access_token}</p>
                <p>Please contact support for assistance.</p>
                <p><a href="/">Back to Home</a></p>
            </body>
            </html>
            """

    @http.route('/payment/debug/test', type='http', auth='public', website=False, csrf=False)
    def debug_test(self, **kwargs):
        """Debug endpoint to test basic functionality"""
        try:
            payment_count = request.env['account.payment'].sudo().search_count([])
            tokens_count = request.env['account.payment'].sudo().search_count([('access_token', '!=', False)])
            
            return f"""
            <html>
            <body>
                <h1>Payment Debug Test</h1>
                <p>Total payments: {payment_count}</p>
                <p>Payments with tokens: {tokens_count}</p>
                <p>Current time: {datetime.datetime.now()}</p>
                <p>Database: {request.env.cr.dbname}</p>
                <p>Status: OK</p>
            </body>
            </html>
            """
        except Exception as e:
            return f"""
            <html>
            <body>
                <h1>Debug Error</h1>
                <p>Error: {str(e)}</p>
            </body>
            </html>
            """
