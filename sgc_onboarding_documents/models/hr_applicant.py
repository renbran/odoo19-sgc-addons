# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import secrets


class OnboardingUploadToken(models.Model):
    _name = 'onboarding.upload.token'
    _description = 'Onboarding Upload Token'
    _rec_name = 'applicant_id'

    applicant_id = fields.Many2one(
        comodel_name='hr.applicant',
        string='Applicant',
        required=True,
        ondelete='cascade',
        help='Applicant for whom this upload token is valid.',
    )
    access_token = fields.Char(
        string='Access Token',
        required=True,
        index=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(24),
        help='Unique token used in the public URL that lets the applicant upload their documents.',
    )

    _sql_constraints = [
        ('access_token_unique', 'unique(access_token)', 'Access token must be unique.'),
    token', 'Access token must be unique.'),
    ]

    @api.model
    def get_or_create_token(self, applicant_id):
        """Return an existing token for the applicant, or create one."""
        token = self.search([('applicant_id', '=', applicant_id)], limit=1)
        if token:
            return token.access_token
        # create new
        rec = self.create({'applicant_id': applicant_id})
        return rec.access_token