# -*- coding: utf-8 -*-
import json
import random
import re
import string
from datetime import datetime, timedelta
from html import escape

from odoo import http
from odoo.http import request, Response


_OTP_EXPIRY_MINUTES = 10


class AMLPublicToolController(http.Controller):

    _otp_sender_default = 'noreply@scholarixglobal.com'
    _otp_reply_to_default = 'info@scholarixglobal.com'

    @http.route('/sanction-check', type='http', auth='public', website=True)
    def sanction_check_page(self, **kwargs):
        return request.render('aml_compliance.public_sanction_check_page')

    @http.route('/sanction-check/search', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def sanction_check_search(self, **kwargs):
        payload = self._payload(kwargs)
        name = (payload.get('name') or '').strip()
        dob = (payload.get('dob') or '').strip()
        gender = (payload.get('gender') or '').strip()
        nationality = (payload.get('nationality') or '').strip()

        if not name:
            return self._json({'success': False, 'error': 'Full name is required.'}, 400)
        if not dob:
            return self._json({'success': False, 'error': 'Date of birth is required.'}, 400)
        if not gender:
            return self._json({'success': False, 'error': 'Gender is required.'}, 400)
        if not nationality:
            return self._json({'success': False, 'error': 'Nationality is required.'}, 400)

        screening_model = request.env['aml.screening.result'].sudo()
        active_hits = screening_model._local_fuzzy_sql(name, limit=20, active=True)
        historical_hits = screening_model._local_fuzzy_sql(name, limit=20, active=False)
        active_hits = sorted(active_hits, key=lambda h: h.get('score', 0.0), reverse=True)
        historical_hits = sorted(historical_hits, key=lambda h: h.get('score', 0.0), reverse=True)

        if active_hits:
            risk_level = 'RED'
            risk_status = 'CURRENTLY_SANCTIONED'
        elif historical_hits:
            risk_level = 'YELLOW'
            risk_status = 'PREVIOUSLY_SANCTIONED'
        else:
            risk_level = 'GREEN'
            risk_status = 'CLEAN'

        # Active records first, then historical records for context.
        hits = active_hits + historical_hits

        response_rows = []
        for h in hits[:10]:
            response_rows.append({
                'listed_name': h.get('listed_name'),
                'list_source': h.get('list_source'),
                'listed_type': h.get('listed_type'),
                'score': round(h.get('score', 0.0), 1),
                'matched_via': h.get('matched_via'),
                'record_status': 'active' if h.get('is_active') else 'historical',
            })

        return self._json({
            'success': True,
            'query': name,
            'dob': dob,
            'gender': gender,
            'nationality': nationality,
            'risk_level': risk_level,
            'risk_status': risk_status,
            'matches': response_rows,
            'total_matches': len(response_rows),
            'current_matches': len(active_hits),
            'historical_matches': len(historical_hits),
        })

    @http.route('/sanction-check/send-otp', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def sanction_check_send_otp(self, **kwargs):
        payload = self._payload(kwargs)
        email = (payload.get('email') or '').strip().lower()
        if not self._is_valid_email(email):
            return self._json({'success': False, 'error': 'Please enter a valid email address.'}, 400)

        otp = ''.join(random.choices(string.digits, k=6))
        expiry = datetime.utcnow() + timedelta(minutes=_OTP_EXPIRY_MINUTES)

        request.session['aml_otp_code'] = otp
        request.session['aml_otp_email'] = email
        request.session['aml_otp_expiry'] = expiry.isoformat()
        request.session['aml_email_verified'] = False

        try:
            params = request.env['ir.config_parameter'].sudo()
            sender = params.get_param('aml.email_sender') or self._otp_sender_default
            reply_to = params.get_param('aml.email_reply_to') or self._otp_reply_to_default
            mail_server_id = self._get_otp_mail_server_id(params)
            mail_vals = {
                'subject': 'Your Sanctions Check Verification Code',
                'email_to': email,
                'email_from': sender,
                'reply_to': reply_to,
                'body_html': (
                    '<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:20px;">'
                    '<h2 style="margin:0 0 8px;color:#111827;">Email Verification</h2>'
                    '<p style="color:#4b5563;margin:0 0 16px;">Use this 6-digit code to verify your email and generate your screening certificate.</p>'
                    f'<div style="font-size:34px;font-weight:800;letter-spacing:10px;color:#0f766e;background:#ecfeff;border:1px solid #a5f3fc;padding:14px 18px;border-radius:10px;display:inline-block;">{otp}</div>'
                    f'<p style="color:#6b7280;margin-top:16px;">This code expires in {_OTP_EXPIRY_MINUTES} minutes.</p>'
                    '</div>'
                ),
                'auto_delete': True,
            }
            if mail_server_id:
                mail_vals['mail_server_id'] = mail_server_id
            request.env['mail.mail'].sudo().create(mail_vals).send()
        except Exception:
            return self._json({'success': False, 'error': 'Unable to send verification code right now. Please try again.'}, 500)

        return self._json({'success': True, 'message': 'Verification code sent to your email.'})

    @http.route('/sanction-check/verify-otp', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def sanction_check_verify_otp(self, **kwargs):
        payload = self._payload(kwargs)
        email = (payload.get('email') or '').strip().lower()
        otp = (payload.get('otp') or '').strip()

        if not email or not otp:
            return self._json({'success': False, 'error': 'Email and verification code are required.'}, 400)

        stored_email = request.session.get('aml_otp_email')
        stored_otp = request.session.get('aml_otp_code')
        stored_expiry = request.session.get('aml_otp_expiry')

        if email != stored_email:
            return self._json({'success': False, 'error': 'This email was not verified. Please request a new code.'}, 400)
        if not stored_expiry or datetime.utcnow() > datetime.fromisoformat(stored_expiry):
            return self._json({'success': False, 'error': 'Verification code expired. Request a new code.'}, 400)
        if otp != stored_otp:
            return self._json({'success': False, 'error': 'Invalid verification code.'}, 400)

        request.session['aml_email_verified'] = True
        request.session['aml_verified_email'] = email
        return self._json({'success': True, 'message': 'Email verified successfully.'})

    @http.route('/sanction-check/signup', type='http', auth='public', website=True, methods=['POST'], csrf=False)
    def sanction_check_signup(self, **kwargs):
        payload = self._payload(kwargs)
        email = (payload.get('email') or '').strip().lower()
        mobile = (payload.get('mobile') or '').strip()
        company_name = (payload.get('company_name') or '').strip()
        person_name = (payload.get('person_name') or '').strip()
        risk_level = (payload.get('risk_level') or 'GREEN').strip().upper()
        risk_status = (payload.get('risk_status') or '').strip().upper()
        total_matches = int(payload.get('total_matches') or 0)
        current_matches = int(payload.get('current_matches') or 0)
        historical_matches = int(payload.get('historical_matches') or 0)
        # Subject passport details from the screening step
        screened_name = (payload.get('screened_name') or '').strip()
        dob = (payload.get('dob') or '').strip()
        gender = (payload.get('gender') or '').strip()
        nationality = (payload.get('nationality') or '').strip()

        if not email or not mobile or not company_name or not person_name:
            return self._json({'success': False, 'error': 'Contact name, company, email, and mobile are required.'}, 400)

        if not self._is_valid_email(email):
            return self._json({'success': False, 'error': 'Please enter a valid email address.'}, 400)

        if not risk_status:
            if risk_level == 'RED':
                risk_status = 'CURRENTLY_SANCTIONED'
            elif risk_level == 'YELLOW':
                risk_status = 'PREVIOUSLY_SANCTIONED'
            else:
                risk_status = 'CLEAN'

        if not request.session.get('aml_email_verified'):
            return self._json({'success': False, 'error': 'Please verify your email before generating certificate.'}, 400)
        if request.session.get('aml_verified_email') != email:
            return self._json({'success': False, 'error': 'Verified email does not match the submitted email.'}, 400)

        source = request.env.ref('aml_compliance.crm_source_aml_sanction_tool', raise_if_not_found=False)
        campaign = request.env.ref('aml_compliance.campaign_aml_sanction_tool', raise_if_not_found=False)
        lead_vals = {
            'name': f'Sanctions Check: {screened_name or person_name}',
            'partner_name': company_name,
            'email_from': email,
            'phone': mobile,
            'type': 'lead',
            'source_id': source.id if source else False,
            'campaign_id': campaign.id if campaign else False,
            'description': (
                f'Lead from Public Sanction Check Tool\n'
                f'--- Subject Details ---\n'
                f'Screened Name: {screened_name or person_name}\n'
                f'Date of Birth: {dob}\n'
                f'Gender: {gender}\n'
                f'Nationality: {nationality}\n'
                f'--- Screening Result ---\n'
                f'Risk Status: {risk_status}\n'
                f'Risk Level: {risk_level}\n'
                f'Current Sanctions Matches: {current_matches}\n'
                f'Historical Sanctions Matches: {historical_matches}\n'
                f'Matches Found: {total_matches}\n'
                f'--- Contact Details ---\n'
                f'Contact Name: {person_name}\n'
                f'Mobile: {mobile}'
            ),
        }

        lead = request.env['crm.lead'].sudo().create(lead_vals)

        certificate_html = self._certificate_html(
            screened_name or person_name, dob, gender, nationality,
            person_name, company_name, email, mobile,
            risk_level, risk_status, total_matches, current_matches, historical_matches
        )

        for key in ('aml_otp_code', 'aml_otp_email', 'aml_otp_expiry', 'aml_email_verified', 'aml_verified_email'):
            request.session.pop(key, None)

        return self._json({
            'success': True,
            'message': 'Lead captured and certificate generated.',
            'lead_id': lead.id,
            'certificate_html': certificate_html,
        })

    def _payload(self, fallback_kwargs):
        data = request.httprequest.get_json(silent=True) if request.httprequest else None
        if isinstance(data, dict):
            return data
        return fallback_kwargs or {}

    def _get_otp_mail_server_id(self, params):
        configured_id = params.get_param('aml.email_mail_server_id')
        if configured_id:
            try:
                server_id = int(configured_id)
                server = request.env['ir.mail_server'].sudo().browse(server_id)
                if server.exists() and server.active:
                    return server.id
            except (TypeError, ValueError):
                pass

        server = request.env['ir.mail_server'].sudo().search([('active', '=', True)], order='sequence,id', limit=1)
        return server.id if server else False

    def _is_valid_email(self, email):
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
            return False
        return True

    def _certificate_html(self, screened_name, dob, gender, nationality,
                          person_name, company_name, email, mobile,
                          risk_level, risk_status, total_matches, current_matches, historical_matches):
        screened_name = escape(screened_name)
        dob = escape(dob)
        gender = escape(gender)
        nationality = escape(nationality)
        person_name = escape(person_name)
        company_name = escape(company_name)
        email = escape(email)
        mobile = escape(mobile)
        risk_level = escape(risk_level)
        risk_status = escape(risk_status)
        generated_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        certificate_id = datetime.utcnow().strftime('SC-%Y%m%d-%H%M%S')
        risk_cls = 'bad' if risk_level == 'RED' else ('warn' if risk_level == 'YELLOW' else 'ok')
        status_map = {
            'CURRENTLY_SANCTIONED': ('Currently Sanctioned', 'bad'),
            'PREVIOUSLY_SANCTIONED': ('Previously Sanctioned (Historical)', 'warn'),
            'CLEAN': ('No Sanctions Record Found', 'ok'),
        }
        status_label, status_cls = status_map.get(risk_status, (risk_status or 'Status Not Available', risk_cls))
        return f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Sanctions Screening Certificate — {screened_name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #1f2937; background: #f9fafb; }}
    .card {{ border: 2px solid #800020; border-radius: 12px; padding: 28px; background: #fff; max-width: 720px; margin: 0 auto; }}
    .header {{ display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #e5e7eb; padding-bottom: 16px; margin-bottom: 20px; }}
    .title {{ color: #800020; font-size: 26px; margin: 0 0 4px; }}
    .sub {{ color: #6b7280; margin: 0; font-size: 14px; }}
    .cert-id {{ font-size: 12px; color: #9ca3af; text-align:right; }}
    .section-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #9ca3af; margin: 18px 0 8px; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px; }}
    .field {{ margin: 4px 0; font-size: 14px; }}
    .field span {{ color: #6b7280; display: block; font-size: 11px; }}
    .risk-line {{ margin: 16px 0 0; font-size: 16px; }}
    .status-line {{ margin: 10px 0 0; font-size: 16px; }}
    .status-chip {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 13px; }}
    .ok {{ color: #059669; font-weight: 700; }}
    .warn {{ color: #d97706; font-weight: 700; }}
    .bad {{ color: #dc2626; font-weight: 700; }}
    .ok.status-chip {{ background: #dcfce7; color: #166534; }}
    .warn.status-chip {{ background: #fef3c7; color: #92400e; }}
    .bad.status-chip {{ background: #fee2e2; color: #991b1b; }}
    .disclaimer {{ margin-top: 20px; padding-top: 14px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #9ca3af; }}
    @media print {{ body {{ background: #fff; margin: 20px; }} }}
  </style>
</head>
<body>
  <div class=\"card\">
    <div class=\"header\">
      <div>
        <h1 class=\"title\">Sanctions Screening Certificate</h1>
        <p class=\"sub\">Issued by Scholarix Global Consultants</p>
      </div>
      <div class=\"cert-id\">Certificate ID<br/><strong>{certificate_id}</strong><br/>{generated_at}</div>
    </div>

    <div class=\"section-label\">Subject Details (as per passport / official ID)</div>
    <div class=\"grid\">
      <div class=\"field\"><span>Full Name</span><strong>{screened_name}</strong></div>
      <div class=\"field\"><span>Date of Birth</span><strong>{dob}</strong></div>
      <div class=\"field\"><span>Gender</span><strong>{gender}</strong></div>
      <div class=\"field\"><span>Nationality</span><strong>{nationality}</strong></div>
    </div>

        <div class=\"section-label\">Screening Result</div>
        <div class=\"grid\">
            <div class=\"field\"><span>Current Sanctions Matches</span><strong>{current_matches}</strong></div>
            <div class=\"field\"><span>Historical Sanctions Matches</span><strong>{historical_matches}</strong></div>
            <div class=\"field\"><span>Total Watchlist Matches</span><strong>{total_matches}</strong></div>
            <div class=\"field\"><span>Report Status</span><strong>{status_label}</strong></div>
        </div>
        <div class=\"risk-line\">Risk Assessment: <span class=\"{risk_cls}\">{risk_level}</span></div>
        <div class=\"status-line\">Sanctions Status: <span class=\"{status_cls} status-chip\">{status_label}</span></div>

    <div class=\"section-label\">Requesting Party</div>
    <div class=\"grid\">
      <div class=\"field\"><span>Name</span><strong>{person_name}</strong></div>
      <div class=\"field\"><span>Company</span><strong>{company_name}</strong></div>
      <div class=\"field\"><span>Email</span><strong>{email}</strong></div>
      <div class=\"field\"><span>Mobile</span><strong>{mobile}</strong></div>
    </div>

    <div class=\"disclaimer\">This certificate is generated for preliminary compliance screening support and does not constitute a regulated compliance determination. It does not replace due diligence obligations under applicable AML/CFT regulations.</div>
  </div>
</body>
</html>
"""

    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type='application/json; charset=utf-8',
        )
