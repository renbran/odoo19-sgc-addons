# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    onboarding_access_token = fields.Char(
        string='Onboarding Upload Token',
        index=True,
        copy=False,
        help='Token used in the public URL that lets the candidate upload their '
             'passport, Emirates ID, visa, education certificate and photo. '
             'Uploaded files are attached to this applicant\'s chatter log.',
    )

    _sql_constraints = [
        ('onboarding_access_token_unique', 'unique(onboarding_access_token)',
         'Onboarding access token must be unique.'),
    ]

    @api.model
    def _get_or_create_onboarding_token(self, applicant_id):
        """Return an existing token, or create one. Idempotent."""
        applicant = self.browse(applicant_id)
        if applicant.onboarding_access_token:
            return applicant.onboarding_access_token
        import secrets
        token = secrets.token_urlsafe(24)
        applicant.write({'onboarding_access_token': token})
        return token
