from odoo import fields, models


class GamificationBadge(models.Model):
    _inherit = 'gamification.badge'

    point_value = fields.Integer(
        string='Point Value',
        default=0,
        help='Karma points awarded to a user each time this badge is granted.',
    )
