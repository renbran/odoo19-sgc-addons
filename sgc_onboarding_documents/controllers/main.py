# -*- coding: utf-8 -*-
"""
Public document upload page for onboarding candidates.
- GET  /onboarding/upload/<token>   — render the upload form
- POST /onboarding/upload/<token>   — accept file uploads, write to applicant chatter

Files become `ir.attachment` records, posted as `mail.message` entries on the
candidate's `hr.applicant` chatter. HR sees them on the "log" of the applicant.
"""
import logging
import base64
from odoo import http, _, SUPERUSER_ID
from odoo.http import request, content_disposition

_logger = logging.getLogger(__name__)

# Document types — each maps to a friendly label shown on the form
DOC_TYPES = [
    ('passport', 'Passport', 'Passport — clear scan of the bio-data page'),
    ('emirates_id', 'Emirates ID', 'Emirates ID — front and back (if issued)'),
    ('visa', 'Visa / Residence Permit', 'Visa or residence permit (if applicable)'),
    ('education', 'Education Certificate', 'Highest education certificate / diploma'),
    ('photo', 'Photo', 'Recent passport-size photo (white background)'),
]


def _attach_to_chatter(applicant, doc_type, file_storage, hr_partner_id):
    """Attach a single uploaded file to the applicant record's chatter."""
    if not file_storage or not file_storage.filename:
        return None
    label = next((l for k, l, _ in DOC_TYPES if k == doc_type), doc_type)
    attachment = request.env['ir.attachment'].sudo().create({
        'name': f"{label} — {file_storage.filename}",
        'datas': base64.b64encode(file_storage.read()),
        'res_model': 'hr.applicant',
        'res_id': applicant.id,
        'type': 'binary',
    })
    # Post a chatter message so it shows up in the log
    body = f"<p><strong>{label}</strong> uploaded by the candidate.</p>"
    applicant.with_user(SUPERUSER_ID).message_post(
        body=body,
        subject=f"Document received: {label}",
        message_type='comment',
        subtype_xmlid='mail.mt_note',
        author_id=hr_partner_id,
        attachment_ids=[(4, attachment.id)],
    )
    return attachment


class OnboardingUploadController(http.Controller):

    @http.route('/onboarding/upload/<string:token>', type='http', auth='public',
                methods=['GET'], website=True, csrf=False)
    def upload_form(self, token, **kwargs):
        Applicant = request.env['hr.applicant'].sudo()
        applicant = Applicant.search([('onboarding_access_token', '=', token)], limit=1)
        if not applicant:
            return request.render(
                'sgc_onboarding_documents.upload_invalid',
                {'token': token, 'doc_types': DOC_TYPES},
                status=404,
            )

        # Check if uploads already exist
        existing = request.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'hr.applicant'),
             ('res_id', '=', applicant.id)],
            ['name', 'create_date'],
            order='create_date desc',
        )
        return request.render(
            'sgc_onboarding_documents.upload_form',
            {
                'token': token,
                'applicant': applicant,
                'doc_types': DOC_TYPES,
                'existing': existing,
            },
        )

    @http.route('/onboarding/upload/<string:token>', type='http', auth='public',
                methods=['POST'], website=True, csrf=False)
    def upload_submit(self, token, **post):
        Applicant = request.env['hr.applicant'].sudo()
        applicant = Applicant.search([('onboarding_access_token', '=', token)], limit=1)
        if not applicant:
            return request.render(
                'sgc_onboarding_documents.upload_invalid',
                {'token': token, 'doc_types': DOC_TYPES},
                status=404,
            )

        # HR partner for the chatter author (so it shows as posted by HR)
        hr_partner = request.env['res.users'].sudo().search(
            [('login', '=', 'hr@sgctech.ai')], limit=1
        ).partner_id
        hr_partner_id = hr_partner.id if hr_partner else SUPERUSER_ID

        uploaded = []
        for doc_key, _, _ in DOC_TYPES:
            f = request.httprequest.files.get(doc_key)
            if f and getattr(f, 'filename', None):
                att = _attach_to_chatter(applicant, doc_key, f, hr_partner_id)
                if att:
                    uploaded.append(doc_key)

        # Render the thank-you page
        existing = request.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'hr.applicant'),
             ('res_id', '=', applicant.id)],
            ['name', 'create_date'],
            order='create_date desc',
        )
        return request.render(
            'sgc_onboarding_documents.upload_thanks',
            {
                'token': token,
                'applicant': applicant,
                'doc_types': DOC_TYPES,
                'uploaded_keys': set(uploaded),
                'existing': existing,
            },
        )
