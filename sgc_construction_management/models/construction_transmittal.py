# -*- coding: utf-8 -*-
from odoo import api, fields, models
import datetime

class ConstructionTransmittal(models.Model):
    _name = 'construction.transmittal'
    _description = 'Document Transmittal'
    _inherit = ['mail.thread']
    _order = 'number desc, id desc'

    name = fields.Char('Subject', required=True, tracking=True)
    number = fields.Char('Transmittal Number', readonly=True, copy=False, index=True)
    project_id = fields.Many2one('construction.project', string='Project', required=True, index=True)
    recipient_id = fields.Many2one('res.partner', string='Recipient', required=True)
    issue_date = fields.Date(default=fields.Date.context_today, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('received', 'Received'),
        ('acknowledged', 'Acknowledged'),
    ], default='draft', tracking=True)
    document_ids = fields.Many2many('construction.document', string='Documents Included')
    remarks = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('number'):
                project = self.env['construction.project'].browse(vals.get('project_id'))
                year = datetime.datetime.now().year
                prefix = f"{project.ref or 'PROJ'}-TRN-{year}"

                # Project-Specific Sequence logic
                last_trn = self.search([
                    ('project_id', '=', project.id)
                ], order='id desc', limit=1)

                next_seq = 1
                if last_trn and last_trn.number:
                    try:
                        last_seq_str = last_trn.number.split('-')[-1]
                        next_seq = int(last_seq_str) + 1
                    except:
                        pass

                vals['number'] = f"{prefix}-{str(next_seq).zfill(4)}"
        return super().create(vals_list)

    def action_issue(self):
        self.state = 'issued'
        for doc in self.document_ids:
            doc.write({
                'status': 'issued',
                'transmittal_id': self.id
            })

    def action_receive(self):
        self.state = 'received'

    def action_acknowledge(self):
        self.state = 'acknowledged'
