from odoo import api, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        # New internal user -> if an employee already exists for that login,
        # generate the branded signature right away.
        for user in users:
            if user.share:
                continue
            employee = self.env['hr.employee'].search(
                [('work_email', '=ilike', user.login or '')], limit=1)
            employee._update_email_signature()
        return users