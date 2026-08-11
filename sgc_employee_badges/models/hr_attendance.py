from odoo import fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    x_excused_late = fields.Boolean(
        string='Excused Late',
        default=False,
        help='Documented transport/medical reason for a late check-in. '
             'Excluded from the Policy Enforcer punctuality calculation '
             'on both sides -- neither counted as on-time nor held against it.',
    )
