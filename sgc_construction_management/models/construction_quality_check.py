# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionQualityCheck(models.Model):
    _name = 'construction.quality.check'
    _description = 'Quality Check'
    _inherit = ['mail.thread']
    company_id = fields.Many2one('res.company', index=True, string='Company', required=True, default=lambda self: self.env.company)

    name = fields.Char(required=True)
    ref = fields.Char(readonly=True, default='New')
    project_id = fields.Many2one('construction.project', index=True, required=True)
    work_order_id = fields.Many2one('construction.work.order', index=True, domain="[('project_id','=',project_id)]")
    wbs_id = fields.Many2one('construction.wbs', index=True, domain="[('project_id','=',project_id)]")
    check_date = fields.Date(default=lambda self: fields.Date.context_today(self))
    inspector_id = fields.Many2one('res.users', index=True, string='Inspector')
    check_type = fields.Selection([
        ('material', 'Material Inspection'),
        ('workmanship', 'Workmanship'),
        ('structural', 'Structural'),
        ('safety', 'Safety'),
        ('final', 'Final Inspection'),
    ], default='workmanship')
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
    ], tracking=True)
    remarks = fields.Text()
    corrective_action = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ], default='draft', tracking=True)
    checklist_ids = fields.One2many('construction.quality.checklist', 'check_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('ref', 'New') == 'New':
                vals['ref'] = self.env['ir.sequence'].next_by_code('construction.quality.check') or 'New'
        return super().create(vals_list)

    def action_start(self):
        self.state = 'in_progress'

    def action_pass(self):
        self.write({'state': 'completed', 'result': 'pass'})

    def action_fail(self):
        self.write({'state': 'failed', 'result': 'fail'})

    def action_reset(self):
        self.state = 'draft'

    def _get_blocking_failures(self, project_id, wbs_ids=None):
        """Failed checks that should block billing for the given scope.

        A failed check with no WBS phase set is a project-wide hold (e.g. a
        failed safety audit) and always blocks. A failed check tied to a
        specific WBS phase only blocks billing for that same phase, matching
        how real contractors scope quality holds to the affected work package
        rather than freezing the whole project's billing.
        """
        domain = [('project_id', '=', project_id), ('state', '=', 'failed')]
        if wbs_ids:
            domain += ['|', ('wbs_id', '=', False), ('wbs_id', 'in', wbs_ids)]
        else:
            domain += [('wbs_id', '=', False)]
        return self.search(domain)


class ConstructionQualityChecklist(models.Model):
    _name = 'construction.quality.checklist'
    _description = 'Quality Checklist Item'

    check_id = fields.Many2one('construction.quality.check', index=True, ondelete='cascade')
    description = fields.Char(required=True)
    is_checked = fields.Boolean()
    remarks = fields.Char()
