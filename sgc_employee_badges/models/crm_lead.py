from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    x_revived_by_id = fields.Many2one(
        'res.users', string='Revived By', readonly=True, copy=False,
        help='Set automatically when this lead is reactivated after having been lost.',
    )
    x_revived_date = fields.Datetime(string='Revived On', readonly=True, copy=False)

    def write(self, vals):
        revived = self.env['crm.lead']
        if vals.get('active'):
            revived = self.filtered(lambda l: not l.active and l.lost_reason_id)
        result = super().write(vals)
        if revived:
            revived.write({
                'x_revived_by_id': self.env.uid,
                'x_revived_date': fields.Datetime.now(),
            })
        return result
