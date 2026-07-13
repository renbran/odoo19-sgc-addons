# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsersExtended(models.Model):
    _inherit = 'res.users'

    allowed_to_learn = fields.Boolean(
        string='Allowed to Learn',
        default=False,
        help='If checked, user can enroll and attempt e-learning quizzes'
    )
