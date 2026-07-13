# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PaymentWorkflowStage(models.Model):
    _name = 'payment.workflow.stage'
    _description = 'Payment Workflow Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    code = fields.Char(string='Stage Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description', translate=True)
    
    is_initial_stage = fields.Boolean(string='Initial Stage')
    is_final_stage = fields.Boolean(string='Final Stage')
    allow_edit = fields.Boolean(string='Allow Edit', default=True)
    require_approval = fields.Boolean(string='Require Approval')
    
    approval_group_ids = fields.Many2many('res.groups', string='Approval Groups')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    
    @api.constrains('is_initial_stage')
    def _check_single_initial_stage(self):
        for record in self:
            if record.is_initial_stage:
                existing = self.search([
                    ('is_initial_stage', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id),
                ])
                if existing:
                    raise ValidationError(_("Only one initial stage allowed per company"))
