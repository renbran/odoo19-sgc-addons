# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ConstructionWBS(models.Model):
    _name = 'construction.wbs'
    _description = 'WBS Phase'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Char()
    project_id = fields.Many2one('construction.project', index=True, required=True, ondelete='cascade')
    parent_id = fields.Many2one('construction.wbs', index=True, string='Parent Phase')
    child_ids = fields.One2many('construction.wbs', 'parent_id', string='Sub-phases')
    sequence = fields.Integer(default=10)
    planned_start = fields.Date()
    planned_end = fields.Date()
    actual_start = fields.Date()
    actual_end = fields.Date()
    progress = fields.Float('Progress %', digits=(5, 2))
    state = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('delayed', 'Delayed'),
    ], default='planned', tracking=True)
    responsible_id = fields.Many2one('res.users', index=True, string='Responsible')
    planned_cost = fields.Monetary(currency_field='currency_id')
    actual_cost = fields.Monetary(compute='_compute_actual_cost', store=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', index=True, related='project_id.currency_id')
    work_order_ids = fields.One2many('construction.work.order', 'wbs_id')
    notes = fields.Text()

    @api.constrains('parent_id')
    def _check_wbs_recursion(self):
        if not self._check_recursion():
            raise ValidationError('Error! You cannot create recursive WBS phases.')

    @api.depends('work_order_ids.actual_cost')
    def _compute_actual_cost(self):
        for rec in self:
            rec.actual_cost = sum(rec.work_order_ids.mapped('actual_cost'))

    def action_start(self):
        self.write({'state': 'in_progress', 'actual_start': fields.Date.context_today(self)})

    def action_complete(self):
        self.write({'state': 'completed', 'actual_end': fields.Date.context_today(self), 'progress': 100.0})

    def action_delay(self):
        self.state = 'delayed'

    def action_reset(self):
        self.state = 'planned'
