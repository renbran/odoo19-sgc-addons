from odoo import models, fields, api, _

class PaymentDashboard(models.Model):
    _name = 'payment.dashboard'
    _description = 'Payment Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Dashboard Name', required=True, default=_('Payment Dashboard'))
    total_payments = fields.Float(string='Total Payments', compute='_compute_totals', store=True)
    total_approved = fields.Float(string='Total Approved', compute='_compute_totals', store=True)
    total_pending = fields.Float(string='Total Pending', compute='_compute_totals', store=True)

    @api.depends('name')
    def _compute_totals(self):
        for rec in self:
            payment_model = self.env['account.payment']
            rec.total_payments = payment_model.search_count([])
            rec.total_approved = payment_model.search_count([('approval_state', '=', 'approved')])
            rec.total_pending = payment_model.search_count([('approval_state', '=', 'pending')])
