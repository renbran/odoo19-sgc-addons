# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import datetime

class ConstructionDocumentFolder(models.Model):
    _name = 'construction.document.folder'
    _description = 'Document Folder'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    parent_id = fields.Many2one('construction.document.folder', string='Parent Folder', ondelete='cascade')
    child_ids = fields.One2many('construction.document.folder', 'parent_id', string='Sub-folders')
    project_id = fields.Many2one('construction.project', string='Project', ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    document_count = fields.Integer(compute='_compute_document_count')

    def _compute_document_count(self):
        for rec in self:
            rec.document_count = self.env['construction.document'].search_count([('folder_id', 'child_of', rec.id)])

class ConstructionDocument(models.Model):
    _name = 'construction.document'
    _description = 'Construction Document'
    _inherit = ['mail.thread']
    _order = 'number desc, id desc'

    name = fields.Char(required=True, tracking=True)
    number = fields.Char('Document Number', readonly=True, copy=False, index=True)
    project_id = fields.Many2one('construction.project', string='Project', required=True, index=True, tracking=True)
    folder_id = fields.Many2one('construction.document.folder', string='Folder', domain="[('project_id', '=', project_id)]", index=True)
    category = fields.Selection([
        ('CON', 'Contract'),
        ('DWG', 'Drawing'),
        ('BOQ', 'BOQ'),
        ('VO', 'Variation Order'),
        ('RFI', 'Request for Info'),
        ('SUB', 'Submittal'),
        ('MAR', 'Material Approval'),
        ('WMS', 'Method Statement'),
        ('WIR', 'Inspection Request'),
        ('NCR', 'Non-Conformance'),
        ('DIA', 'Site Diary'),
        ('REP', 'Progress Report'),
        ('BIL', 'Billing'),
        ('INV', 'Invoice'),
        ('PAY', 'Payment'),
        ('PRO', 'Procurement'),
        ('PO', 'Purchase Order'),
        ('VEN', 'Vendor Document'),
        ('HSE', 'HSE'),
        ('QA', 'QAQC'),
        ('EQU', 'Equipment'),
        ('LAB', 'Labor'),
        ('TS', 'Timesheet'),
        ('PHO', 'Photo'),
        ('COR', 'Correspondence'),
        ('TRN', 'Transmittal'),
    ], string='Category', required=True, tracking=True)

    current_revision_id = fields.Many2one('construction.document.revision', string='Current Revision', readonly=True, copy=False)
    revision_no = fields.Char(related='current_revision_id.revision_no', string='Revision')
    status = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('closed', 'Closed'),
    ], default='draft', tracking=True)
    issue_date = fields.Date(default=fields.Date.context_today)
    amount = fields.Monetary(string='Amount', currency_field='currency_id', help='Value of the document, e.g. the variation amount for a Variation Order.')
    currency_id = fields.Many2one('res.currency', related='project_id.currency_id')
    transmittal_id = fields.Many2one('construction.transmittal', string='Transmittal', readonly=True)
    revision_ids = fields.One2many('construction.document.revision', 'document_id', string='Revisions')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments', compute='_compute_attachments')

    def _compute_attachments(self):
        for rec in self:
            rec.attachment_ids = rec.revision_ids.mapped('attachment_id')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('number'):
                project = self.env['construction.project'].browse(vals.get('project_id'))
                category = vals.get('category')
                year = datetime.datetime.now().year
                prefix = f"{project.ref or 'PROJ'}-{category}-{year}"

                # Project-Specific Sequence logic
                # Find the last document for this project and category to determine next number
                last_doc = self.search([
                    ('project_id', '=', project.id),
                    ('category', '=', category)
                ], order='id desc', limit=1)

                next_seq = 1
                if last_doc and last_doc.number:
                    try:
                        # Extract the last 4 digits from the number (e.g. PROJECT-CAT-2026-0005 -> 5)
                        last_seq_str = last_doc.number.split('-')[-1]
                        next_seq = int(last_seq_str) + 1
                    except:
                        pass

                vals['number'] = f"{prefix}-{str(next_seq).zfill(4)}"
        return super().create(vals_list)

class ConstructionDocumentRevision(models.Model):
    _name = 'construction.document.revision'
    _description = 'Document Revision'
    _order = 'create_date desc'

    document_id = fields.Many2one('construction.document', string='Document', required=True, ondelete='cascade')
    revision_no = fields.Char('Revision No.', required=True, default='0')
    revision_date = fields.Date('Revision Date', default=fields.Date.context_today)
    status = fields.Selection([
        ('ifr', 'Issued for Review'),
        ('ifa', 'Issued for Approval'),
        ('ifc', 'Issued for Construction'),
        ('ab', 'As-Built'),
        ('arch', 'Archived'),
    ], string='Status', default='ifr')
    attachment_id = fields.Many2one('ir.attachment', string='Attachment', copy=False)
    file = fields.Binary(string='Upload File')
    file_name = fields.Char(string='File Name')
    prepared_by = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user)
    checked_by = fields.Many2one('res.users', string='Checked By')
    approved_by = fields.Many2one('res.users', string='Approved By')
    remarks = fields.Text()

    @api.constrains('attachment_id', 'file')
    def _check_has_file(self):
        for rec in self:
            if not rec.attachment_id and not rec.file:
                raise ValidationError(_("Upload a file or select an existing attachment for this revision."))

    def _create_attachment_from_file(self, vals):
        # Lets users upload a file straight from their device (the file/
        # file_name Binary fields) instead of only being able to pick a
        # pre-existing ir.attachment record. Turn the upload into a real
        # ir.attachment and point attachment_id at it, so downstream logic
        # (download links, _compute_attachments) keeps working unchanged.
        if vals.get('file') and not vals.get('attachment_id'):
            attachment = self.env['ir.attachment'].create({
                'name': vals.get('file_name') or 'document',
                'datas': vals['file'],
                'res_model': 'construction.document.revision',
            })
            vals['attachment_id'] = attachment.id
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._create_attachment_from_file(vals) for vals in vals_list]
        revisions = super().create(vals_list)
        for rev in revisions:
            rev.document_id.current_revision_id = rev.id
            if rev.attachment_id and rev.attachment_id.res_id != rev.id:
                rev.attachment_id.write({'res_id': rev.id})
        return revisions

    def write(self, vals):
        if vals.get('file') and not vals.get('attachment_id'):
            vals = self._create_attachment_from_file(dict(vals))
        return super().write(vals)
