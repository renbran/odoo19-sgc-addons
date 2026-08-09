# -*- coding: utf-8 -*-
"""
Public onboarding document upload for hiring candidates.

- GET  /onboarding/upload/<token>  — render the upload form
- POST /onboarding/upload/<token>  — validated file upload, written to the
  applicant chatter as ``ir.attachment`` records on ``hr.applicant``.

Security notes:
- The token authenticates the candidate; it is stored hashed-free on the
  applicant record (standard Odoo portal-token pattern) and expires after a
  configurable TTL (``sgc_onboarding.token_ttl_days``, default 30).
- Post is public (``auth='public'``); everything is done through ``sudo()``
  because anonymous users have no ACLs. Access control is the token itself.
- Files are validated server-side: extension whitelist (PDF/PNG/JPG/JPEG),
  10 MB size cap, non-empty payload.
"""
import base64
import logging
import os

from odoo import SUPERUSER_ID, _, fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Document types (field key, friendly label, hint)
DOC_TYPES = [
    ('passport', 'Passport', 'Passport — clear scan of the bio-data page'),
    ('emirates_id', 'Emirates ID', 'Emirates ID — front and back (if issued)'),
    ('visa', 'Visa / Residence Permit', 'Visa or residence permit (if applicable)'),
    ('education', 'Education Certificate', 'Highest education certificate / diploma'),
    ('photo', 'Photo', 'Recent passport-size photo (white background)'),
]

ATTACHMENT_PREFIX = 'Onboarding - '
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg'}


def _validate_upload(file_storage):
    """Validate a werkzeug FileStorage. Returns (error_message, bytes_data)."""
    if not file_storage or not file_storage.filename:
        return _('No file selected.'), None
    ext = os.path.splitext(file_storage.filename or '')[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return _('Only PDF, PNG, JPG or JPEG files are allowed.'), None
    data = file_storage.read()
    if not data:
        return _('The uploaded file is empty.'), None
    if len(data) > MAX_FILE_BYTES:
        return _('File is larger than the 10 MB limit.'), None
    return None, data


class OnboardingUploadController(http.Controller):

    def _applicant_for_token(self, token):
        """Return the applicant for a token, or (None, reason) if not found."""
        token = (token or '').strip()
        if not token:
            return None, 'invalid'
        applicant = request.env['hr.applicant'].sudo().search(
            [('onboarding_access_token', '=', token)], limit=1)
        if not applicant:
            return None, 'invalid'
        if applicant.onboarding_token_expiry and \
                applicant.onboarding_token_expiry <= fields.Datetime.now():
            _logger.warning('Onboarding upload attempted with expired token for applicant %s',
                            applicant.id)
            return None, 'expired'
        return applicant, None

    def _existing_attachments(self, applicant):
        """Attachments previously uploaded through this module."""
        return request.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'hr.applicant'),
             ('res_id', '=', applicant.id),
             ('name', 'like', ATTACHMENT_PREFIX + '%')],
            ['name', 'create_date'],
            order='create_date desc')

    def _render_form(self, applicant, token, errors=None, values=None):
        return request.render('sgc_onboarding_documents.upload_form', {
            'token': token,
            'applicant': applicant,
            'doc_types': DOC_TYPES,
            'existing': self._existing_attachments(applicant),
            'errors': errors or {},
            'values': values or {},
        })

    @http.route('/onboarding/upload/<string:token>', type='http', auth='public',
                methods=['GET'], website=True, csrf=False)
    def upload_form(self, token, **kwargs):
        applicant, reason = self._applicant_for_token(token)
        if not applicant:
            return request.render(
                'sgc_onboarding_documents.upload_invalid',
                {'token': token, 'reason': reason}, status=404)
        return self._render_form(applicant, token)

    @http.route('/onboarding/upload/<string:token>', type='http', auth='public',
                methods=['POST'], website=True, csrf=False)
    def upload_submit(self, token, **post):
        applicant, reason = self._applicant_for_token(token)
        if not applicant:
            return request.render(
                'sgc_onboarding_documents.upload_invalid',
                {'token': token, 'reason': reason}, status=404)

        # Validate every uploaded file first — reject the whole submission if
        # any file is invalid so the candidate can fix the issue in one pass.
        errors = {}
        uploads = {}  # doc_key -> bytes
        for doc_key, _label, _hint in DOC_TYPES:
            f = request.httprequest.files.get(doc_key)
            if f and f.filename:
                error, data = _validate_upload(f)
                if error:
                    errors[doc_key] = error
                else:
                    uploads[doc_key] = data

        if not uploads:
            errors['_global'] = _('Please upload at least one valid document.')

        if errors:
            _logger.warning('Onboarding upload rejected for applicant %s: %s', applicant.id, errors)
            return self._render_form(applicant, token, errors=errors)

        # HR partner used as the chatter author (so posts show as coming from HR)
        hr_partner = request.env['res.users'].sudo().search(
            [('login', '=', 'hr@sgctech.ai')], limit=1
        ).partner_id
        hr_partner_id = hr_partner.id if hr_partner \
            else request.env.ref('base.partner_root').id

        uploaded = []
        for doc_key, label, _hint in DOC_TYPES:
            data = uploads.get(doc_key)
            if not data:
                continue
            f = request.httprequest.files.get(doc_key)
            attachment = request.env['ir.attachment'].sudo().create({
                'name': f'{ATTACHMENT_PREFIX}{label} - {f.filename}',
                'datas': base64.b64encode(data),
                'res_model': 'hr.applicant',
                'res_id': applicant.id,
                'type': 'binary',
            })
            body = f"<p><strong>{label}</strong> uploaded by the candidate.</p>"
            applicant.with_user(SUPERUSER_ID).message_post(
                body=body,
                subject=f"Document received: {label}",
                message_type='comment',
                subtype_xmlid='mail.mt_note',
                author_id=hr_partner_id,
                attachment_ids=[attachment.id],
            )
            uploaded.append({'key': doc_key, 'label': label})

        _logger.info('Onboarding upload accepted for applicant %s: %d file(s)',
                     applicant.id, len(uploaded))
        return request.render('sgc_onboarding_documents.upload_thanks', {
            'token': token,
            'applicant': applicant,
            'doc_types': DOC_TYPES,
            'uploaded': uploaded,
            'existing': self._existing_attachments(applicant),
        })