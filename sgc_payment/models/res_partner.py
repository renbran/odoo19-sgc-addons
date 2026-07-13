# models/res_partner.py
from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    payment_count = fields.Integer(
        string="Payment Count",
        compute='_compute_payment_count',
        help="Total number of payments with this partner"
    )
    
    @api.depends('name')
    def _compute_payment_count(self):
        for partner in self:
            partner.payment_count = self.env['account.payment'].search_count([
                ('partner_id', '=', partner.id),
                ('state', 'in', ['posted', 'sent', 'reconciled'])
            ])
    
    def action_view_partner_payments(self):
        """View payments for this partner"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Payments for %s') % self.display_name,
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }