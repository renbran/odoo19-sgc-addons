# -*- coding: utf-8 -*-
"""Onboarding document upload for HR applicants.

A token-backed public URL (``/onboarding/upload/<token>``) lets a candidate
upload their own day-one documents (passport, Emirates ID, visa, education
certificates, photo). Files are stored as ``ir.attachment`` records bound on
the ``hr.applicant`` chatter so HR can review them on the applicant record.

The token and its expiry live directly on ``hr.applicant`` so HR can
generate/reset/send the link from the applicant form.
"""
import logging
import secrets
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

DEFAULT_TOKEN_TTL_DAYS = 30


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    onboarding_access_token = fields.Char(
        string='Onboarding Token',
        copy=False,
        index=True,
        default=lambda self: secrets.token_urlsafe(32),
        help='Secret token used in the public onboarding upload URL.',
    )
    onboarding_token_expiry = fields.Datetime(
        string='Onboarding Link Expiry',
        copy=False,
        default=lambda self: self._default_onboarding_expiry(),
        help='After this date the public upload link stops working.',
    )
    onboarding_link = fields.Char(
        string='Onboarding Upload Link',
        compute='_compute_onboarding_link',
        help='Public URL the applicant uses to upload their documents.',
    )

    @api.model
    def _get_onboarding_ttl_days(self):
        """Return the token lifetime in days (configurable via ir.config_parameter)."""
        param = self.env['ir.config_parameter'].sudo().get_param(
            'sgc_onboarding.token_ttl_days', DEFAULT_TOKEN_TTL_DAYS)
        try:
            return max(1, int(param))
        except (TypeError, ValueError):
            return DEFAULT_TOKEN_TTL_DAYS

    @api.model
    def _default_onboarding_expiry(self):
        return fields.Datetime.now() + timedelta(days=self._get_onboarding_ttl_days())

    @api.depends('onboarding_access_token')
    def _compute_onboarding_link(self):
        base_url = self.get_base_url()
        for rec in self:
            rec.onboarding_link = (
                rec.onboarding_access_token
                and '%s/onboarding/upload/%s' % (base_url, rec.onboarding_access_token)
                or False
            )

    def _ensure_onboarding_token(self):
        """Return the stored token, recreating it (with a fresh expiry) when
        missing or expired. Callers must ensure_single record."""
        self.ensure_one()
        self._check_access('write')
        now = fields.Datetime.now()
        expired = bool(self.onboarding_token_expiry and self.onboarding_token_expiry <= now)
        if not self.onboarding_access_token or expired:
            self.write({
                'onboarding_access_token': secrets.token_urlsafe(32),
                'onboarding_token_expiry': self._default_onboarding_expiry(),
            })
        return self.onboarding_access_token

    def action_generate_onboarding_link(self):
        """Generate (or refresh) the onboarding upload link for this applicant."""
        self.ensure_one()
        self._ensure_onboarding_token()
        self._log_onboarding_link('generated')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Onboarding link generated'),
                'message': self.onboarding_link,
                'type': 'success',
                'sticky': True,
                'next': False,
            },
        }

    def action_send_onboarding_link(self):
        """Email the onboarding upload link to the applicant."""
        self.ensure_one()
        self._ensure_onboarding_token()
        if not self.email_from:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No email on the applicant'),
                    'message': _('Add an email address to the applicant before sending the link.'),
                    'type': 'warning',
                    'sticky': True,
                },
            }
        template = self.env.ref(
            'sgc_onboarding_documents.onboarding_link_email_template')
        template.send_mail(self.id, force_send=False)
        self.message_post(
            body=_('Onboarding upload link e-mailed to %(email)s.') % {'email': self.email_from},
            message_type='note',
            subtype_xmlid='mail.mt_note',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Link sent'),
                'message': _('Onboarding link sent to %s') % self.email_from,
                'type': 'success',
                'sticky': False,
            },
        }

    def _log_onboarding_link(self, action):
        self.ensure_one()
        body = (
            '<p>Onboarding link (%s), valid until <b>%s</b>:</p>'
            '<p><a href="%s">%s</a></p>'
        ) % (action, self.onboarding_token_expiry, self.onboarding_link, self.onboarding_link)
        self.message_post(body=body, message_type='note', subtype_xmlid='mail.mt_note')