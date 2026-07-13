# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ConstructionHSEIncident(models.Model):
    _name = 'construction.hse.incident'
    _description = 'HSE Incident/Event'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char('Incident Title', required=True, tracking=True)
    project_id = fields.Many2one('construction.project', string='Project', required=True, index=True)
    date = fields.Datetime(default=fields.Datetime.now, tracking=True)
    incident_type = fields.Selection([
        ('near_miss', 'Near Miss'),
        ('first_aid', 'First Aid'),
        ('lti', 'Lost Time Injury (LTI)'),
        ('violation', 'Safety Violation'),
        ('tbt', 'Toolbox Talk'),
        ('inspection', 'Safety Inspection'),
    ], default='near_miss', required=True, tracking=True)
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], default='low', tracking=True)
    description = fields.Text('Description', required=True)
    corrective_action = fields.Text('Corrective Action')
    status = fields.Selection([
        ('open', 'Open'),
        ('investigating', 'Under Investigation'),
        ('closed', 'Closed'),
    ], default='open', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    reported_by = fields.Many2one('res.users', string='Reported By', default=lambda self: self.env.user)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def action_investigate(self):
        self.status = 'investigating'

    def action_close(self):
        self.status = 'closed'
