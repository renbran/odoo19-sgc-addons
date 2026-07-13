# -*- coding: utf-8 -*-
"""
KYC Portal Controller
Public-facing KYC application form — no login required.
Routes:
  GET/POST /contact/kyc              → multi-step form (also /kyc/apply)
  POST     /contact/kyc/send-otp    → send 6-digit OTP to email (JSON)
  POST     /contact/kyc/verify-otp  → verify OTP entered by user (JSON)
  GET      /kyc/success/<token>      → submission confirmation
  GET      /kyc/status/<token>       → check application status (public)
"""

import base64
import logging
import random
import string
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 10


class KYCPortalController(http.Controller):

    # ─────────────────────────────────────────────────────────────
    # POST /contact/kyc/send-otp  — generate & email OTP (JSON)
    # ─────────────────────────────────────────────────────────────
    @http.route('/contact/kyc/send-otp', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def kyc_send_otp(self, email=None, **kw):
        if not email or '@' not in email:
            return {'success': False, 'error': 'Please enter a valid email address.'}

        email = email.strip().lower()

        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        expiry = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

        # Store in session
        request.session['kyc_otp'] = otp
        request.session['kyc_otp_email'] = email
        request.session['kyc_otp_expiry'] = expiry
        request.session['kyc_email_verified'] = False

        # Send email via Odoo mail
        try:
            email_sender = request.env['ir.config_parameter'].sudo().get_param('kyc.email_sender') or request.env.user.company_id.email or 'noreply@example.com'
            mail_vals = {
                'subject': 'Your OSUS KYC Email Verification Code',
                'email_to': email,
                'email_from': email_sender,
                'body_html': f"""
                <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;padding:20px;">
                  <div style="background:#800020;padding:20px 24px;border-radius:10px 10px 0 0;text-align:center;">
                    <h2 style="color:#fff;margin:0;font-size:1.3rem;">&#128272; Email Verification</h2>
                    <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:.9rem;">OSUS Real Estate Brokerage LLC</p>
                  </div>
                  <div style="background:#fff;border:1px solid #e5e7eb;border-top:none;padding:28px 24px;border-radius:0 0 10px 10px;">
                    <p style="color:#374151;font-size:.95rem;">You are submitting a KYC application. Use the code below to verify your email address:</p>
                    <div style="background:#f9fafb;border:2px dashed #800020;border-radius:10px;padding:20px;text-align:center;margin:20px 0;">
                      <div style="font-size:2.5rem;font-weight:800;letter-spacing:12px;color:#800020;">{otp}</div>
                      <p style="color:#6b7280;font-size:.8rem;margin:8px 0 0;">Valid for {OTP_EXPIRY_MINUTES} minutes</p>
                    </div>
                    <p style="color:#6b7280;font-size:.82rem;">If you did not request this, please ignore this email.</p>
                    <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0;"/>
                    <p style="color:#9ca3af;font-size:.75rem;text-align:center;">
                             Scholarix Global Consultants &nbsp;|&nbsp; +971-52-198-5231 &nbsp;|&nbsp; info@sgctech.ai
                    </p>
                  </div>
                </div>""",
                'auto_delete': True,
            }
            mail = request.env['mail.mail'].sudo().create(mail_vals)
            mail.send()
            _logger.info("KYC OTP sent to %s", email)
        except Exception as e:
            _logger.error("KYC OTP mail failed for %s: %s", email, e)
            return {'success': False, 'error': 'Could not send email. Please try again.'}

        return {'success': True, 'message': f'Verification code sent to {email}'}

    # ─────────────────────────────────────────────────────────────
    # POST /contact/kyc/verify-otp — validate OTP entered (JSON)
    # ─────────────────────────────────────────────────────────────
    @http.route('/contact/kyc/verify-otp', type='jsonrpc', auth='public', website=True, methods=['POST'])
    def kyc_verify_otp(self, email=None, otp=None, **kw):
        if not email or not otp:
            return {'success': False, 'error': 'Missing email or code.'}

        email = email.strip().lower()
        otp = otp.strip()

        stored_otp   = request.session.get('kyc_otp')
        stored_email = request.session.get('kyc_otp_email', '')
        stored_expiry = request.session.get('kyc_otp_expiry')

        if stored_email != email:
            return {'success': False, 'error': 'Email does not match. Please re-send the code.'}

        if not stored_expiry or datetime.utcnow().isoformat() > stored_expiry:
            return {'success': False, 'error': 'Verification code has expired. Please request a new one.'}

        if otp != stored_otp:
            return {'success': False, 'error': 'Incorrect code. Please check your email and try again.'}

        # Mark verified in session
        request.session['kyc_email_verified'] = True
        request.session['kyc_verified_email'] = email
        _logger.info("KYC email verified: %s", email)
        return {'success': True, 'message': 'Email verified successfully!'}

    # ─────────────────────────────────────────────────────────────
    # GET /contact/kyc — render the application form
    # ─────────────────────────────────────────────────────────────
    @http.route(['/contact/kyc', '/kyc/apply'], type='http', auth='public', website=True, methods=['GET'], sitemap=False)
    def kyc_form(self, **kw):
        env = request.env
        countries = env['res.country'].sudo().search([], order='name')
        source_funds = env['kyc.source.funds'].sudo().search([])
        source_wealth = env['kyc.source.wealth'].sudo().search([])
        currencies = env['res.currency'].sudo().search([('active', '=', True)], order='name')
        return request.render('kyc_management.portal_kyc_form', {
            'countries': countries,
            'source_funds': source_funds,
            'source_wealth': source_wealth,
            'currencies': currencies,
            'error': {},
            'values': {},
        })

    # ─────────────────────────────────────────────────────────────
    # POST /kyc/apply — process form submission
    # ─────────────────────────────────────────────────────────────
    @http.route(['/contact/kyc', '/kyc/apply'], type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def kyc_form_submit(self, **post):
        env = request.env
        error = {}
        values = dict(post)

        # ── Email verification check ───────────────────────────
        if not request.session.get('kyc_email_verified'):
            error['email'] = 'Email address must be verified before submitting.'
        elif request.session.get('kyc_verified_email', '').lower() != post.get('email', '').strip().lower():
            error['email'] = 'Verified email does not match. Please re-verify.'

        # ── Required field validation ──────────────────────────
        required = [
            'first_name', 'last_name', 'email', 'phone',
            'date_of_birth', 'gender', 'nationality_id',
            'passport_number', 'passport_expiry_date',
            'residential_address', 'residential_city', 'residential_country_id',
            'employment_status', 'purpose_of_transaction', 'payment_method',
            'annual_income', 'politically_exposed_person',
        ]
        for field in required:
            if not post.get(field):
                error[field] = 'This field is required.'

        # ── Source of funds: at least one checkbox required ────
        funds_list = request.httprequest.form.getlist('source_of_funds_ids')
        if not any(funds_list):
            error['source_of_funds_ids'] = 'Please select at least one source of funds.'

        # ── Identity document: passport OR emirates ID required ─
        passport_file = request.httprequest.files.get('passport_document')
        emirates_file = request.httprequest.files.get('emirates_id_document')
        has_passport = passport_file and passport_file.filename
        has_emirates = emirates_file and emirates_file.filename
        if not has_passport and not has_emirates:
            error['id_document'] = 'Please upload at least one identity document (Passport or Emirates ID).'

        # ── Consent validation ─────────────────────────────────
        for consent in ['consent_terms_conditions', 'consent_privacy_policy',
                        'consent_data_processing', 'consent_aml_kyc']:
            if not post.get(consent):
                error[consent] = 'You must accept this to proceed.'

        # ── Signature validation ───────────────────────────────
        if not post.get('signature_data'):
            error['signature_data'] = 'Please draw your signature.'

        if error:
            countries = env['res.country'].sudo().search([], order='name')
            source_funds = env['kyc.source.funds'].sudo().search([])
            source_wealth = env['kyc.source.wealth'].sudo().search([])
            currencies = env['res.currency'].sudo().search([('active', '=', True)], order='name')
            return request.render('kyc_management.portal_kyc_form', {
                'countries': countries,
                'source_funds': source_funds,
                'source_wealth': source_wealth,
                'currencies': currencies,
                'error': error,
                'values': values,
            })

        # ── Build record vals ──────────────────────────────────
        def _int_or_false(v):
            try:
                return int(v) if v else False
            except (ValueError, TypeError):
                return False

        def _date_or_false(v):
            if not v:
                return False
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                return False

        def _file(field_name):
            f = request.httprequest.files.get(field_name)
            if f and f.filename:
                return base64.b64encode(f.read())
            return False

        def _sig_b64(data_url):
            """Strip data:image/png;base64, prefix from canvas export."""
            if data_url and ',' in data_url:
                return data_url.split(',', 1)[1].encode()
            return data_url.encode() if data_url else False

        # Many2many source_of_funds_ids
        funds_ids = [_int_or_false(i) for i in request.httprequest.form.getlist('source_of_funds_ids') if i]
        funds_ids = list(filter(None, funds_ids))
        wealth_ids = [_int_or_false(i) for i in request.httprequest.form.getlist('source_of_wealth_ids') if i]
        wealth_ids = list(filter(None, wealth_ids))

        # ── Find or create res.partner for this applicant ─────
        email_clean = post.get('email', '').strip().lower()
        first = post.get('first_name', '').strip()
        last  = post.get('last_name', '').strip()
        full_name = f"{first} {last}".strip() or email_clean
        partner = env['res.partner'].sudo().search(
            [('email', '=', email_clean)], limit=1)
        if not partner:
            # Avoid custom unique-name / unique-phone constraints
            existing_name = env['res.partner'].sudo().search(
                [('name', '=ilike', full_name)], limit=1)
            partner_name = full_name if not existing_name else f"{full_name} ({email_clean})"
            partner = env['res.partner'].sudo().create({
                'name': partner_name,
                'email': email_clean,
                'is_company': False,
            })

        vals = {
            'partner_id': partner.id,
            'first_name': first,
            'last_name': last,
            'email': email_clean,
            'phone': post.get('phone', '').strip(),
            'date_of_birth': _date_or_false(post.get('date_of_birth')),
            'gender': post.get('gender'),
            'nationality_id': _int_or_false(post.get('nationality_id')),
            'passport_number': post.get('passport_number', '').strip(),
            'passport_country_id': _int_or_false(post.get('passport_country_id')),
            'passport_issue_date': _date_or_false(post.get('passport_issue_date')),
            'passport_expiry_date': _date_or_false(post.get('passport_expiry_date')),
            'residency_visa_no': post.get('residency_visa_no', '').strip(),
            'residency_expiry_date': _date_or_false(post.get('residency_expiry_date')),
            'place_of_birth': post.get('place_of_birth', '').strip(),
            'aliases': post.get('aliases', '').strip(),
            'emirates_id': post.get('emirates_id', '').strip(),
            'residential_address': post.get('residential_address', '').strip(),
            'residential_city': post.get('residential_city', '').strip(),
            'residential_state': post.get('residential_state', '').strip(),
            'residential_country_id': _int_or_false(post.get('residential_country_id')),
            'residential_postal_code': post.get('residential_postal_code', '').strip(),
            'employment_status': post.get('employment_status'),
            'occupation': post.get('occupation', '').strip(),
            'employer_name': post.get('employer_name', '').strip(),
            'employer_address': post.get('employer_address', '').strip(),
            'years_in_role': _int_or_false(post.get('years_in_role')),
            'source_of_funds_ids': [(6, 0, funds_ids)] if funds_ids else False,
            'source_of_wealth_ids': [(6, 0, wealth_ids)] if wealth_ids else False,
            'purpose_of_transaction': post.get('purpose_of_transaction'),
            'payment_method': post.get('payment_method'),
            'annual_income': float(post.get('annual_income') or 0) or False,
            'currency_id': _int_or_false(post.get('currency_id')),
            'politically_exposed_person': post.get('politically_exposed_person'),
            'pep_details': post.get('pep_details', '').strip(),
            'consent_terms_conditions': bool(post.get('consent_terms_conditions')),
            'consent_privacy_policy': bool(post.get('consent_privacy_policy')),
            'consent_data_processing': bool(post.get('consent_data_processing')),
            'consent_aml_kyc': bool(post.get('consent_aml_kyc')),
            'signature_image': _sig_b64(post.get('signature_data')),
            'signature_timestamp': fields_datetime_now(),
            'signature_location': request.httprequest.environ.get('HTTP_X_FORWARDED_FOR', ''),
            'state': 'submitted',
            'submitted_date': fields_datetime_now(),
            # File uploads — field names match template input name="" attributes
            'passport_document': _file('passport_document'),
            'emirates_id_document': _file('emirates_id_document'),
            'proof_of_address_document': _file('proof_of_address_document'),
        }

        # Remove False file fields so existing records aren't cleared
        vals = {k: v for k, v in vals.items() if v is not False or k in (
            'source_of_funds_ids', 'source_of_wealth_ids',
        )}

        try:
            application = env['kyc.application'].sudo().create(vals)
            # Generate approval token (normally done by action_submit; portal creates directly)
            if not application.approval_token:
                application._generate_approval_token()
            _logger.info("KYC portal submission: %s (id=%d) token=%s",
                         application.kyc_id, application.id, application.approval_token)

            # ── Auto-create CRM lead from KYC submission ─────────
            try:
                source = env.ref('kyc_management.crm_source_kyc_portal', raise_if_not_found=False)
                campaign = env.ref('kyc_management.campaign_kyc_portal', raise_if_not_found=False)
                crm_lead = env['crm.lead'].sudo().create({
                    'name': f'KYC: {full_name}',
                    'email_from': email_clean,
                    'phone': post.get('phone', '').strip(),
                    'partner_name': full_name,
                    'type': 'lead',
                    'source_id': source.id if source else False,
                    'description': f'KYC Application #{application.kyc_id}\nStatus: Submitted\nOccupation: {post.get("occupation", "N/A")}\nAnnual Income: {post.get("annual_income", "N/A")}',
                    'campaign_id': campaign.id if campaign else False,
                })
                application.lead_id = crm_lead.id
                _logger.info("CRM lead created: %d for KYC %s", crm_lead.id, application.kyc_id)
            except Exception as e:
                _logger.warning("CRM lead creation failed for KYC %s: %s", application.kyc_id, e)
            
            # Clear OTP session data
            for k in ('kyc_otp', 'kyc_otp_email', 'kyc_otp_expiry', 'kyc_email_verified', 'kyc_verified_email'):
                request.session.pop(k, None)
        except Exception as e:
            _logger.error("KYC portal create failed: %s", e)
            error['_global'] = 'Submission failed. Please try again or contact support.'
            countries = env['res.country'].sudo().search([], order='name')
            source_funds = env['kyc.source.funds'].sudo().search([])
            source_wealth = env['kyc.source.wealth'].sudo().search([])
            currencies = env['res.currency'].sudo().search([('active', '=', True)], order='name')
            return request.render('kyc_management.portal_kyc_form', {
                'countries': countries,
                'source_funds': source_funds,
                'source_wealth': source_wealth,
                'currencies': currencies,
                'error': error,
                'values': values,
            })

        return request.redirect(f'/kyc/success/{application.approval_token}')

    # ─────────────────────────────────────────────────────────────
    # GET /kyc/success/<token> — submission confirmation
    # ─────────────────────────────────────────────────────────────
    @http.route('/kyc/success/<string:token>', type='http', auth='public', website=True)
    def kyc_success(self, token, **kw):
        application = request.env['kyc.application'].sudo().search(
            [('approval_token', '=', token)], limit=1
        )
        if not application:
            return request.not_found()
        return request.render('kyc_management.portal_kyc_success', {
            'application': application,
        })

    # ─────────────────────────────────────────────────────────────
    # GET /kyc/status/<token> — public status check
    # ─────────────────────────────────────────────────────────────
    @http.route('/kyc/status/<string:token>', type='http', auth='public', website=True)
    def kyc_status(self, token, **kw):
        application = request.env['kyc.application'].sudo().search(
            [('approval_token', '=', token)], limit=1
        )
        if not application:
            return request.not_found()
        return request.render('kyc_management.portal_kyc_status', {
            'application': application,
        })


def fields_datetime_now():
    from odoo import fields
    return fields.Datetime.now()
