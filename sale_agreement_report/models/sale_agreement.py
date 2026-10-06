# -*- coding: utf-8 -*-

import base64
from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleAgreement(models.Model):
    _name = 'sale.agreement'
    _description = 'Yearly Customer Agreement'
    _order = 'agreement_year desc, id desc'

    @api.model
    def _normalize_partner_id(self, partner_id):
        if not partner_id:
            return partner_id
        partner = self.env['res.partner'].browse(partner_id)
        return partner.commercial_partner_id.id

    name = fields.Char(string='Agreement Reference', required=True, copy=False, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, index=True)
    commercial_partner_id = fields.Many2one(
        'res.partner',
        string='Commercial Entity',
        related='partner_id.commercial_partner_id',
        store=True,
        index=True,
        readonly=True,
    )
    agreement_year = fields.Integer(string='Agreement Year', required=True, default=lambda self: date.today().year)
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    sale_order_id = fields.Many2one('sale.order', string='Related Sales Order')

    agreement_date = fields.Date(string='Agreement Date')
    agreement_contact_person = fields.Char(string='Agreement Contact Person')
    agreement_job_title = fields.Char(string='Contact Job Title')
    num_users = fields.Integer(string='Number of Users', default=1)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
    )
    monthly_subscription_amount = fields.Monetary(
        string='Monthly Subscription Amount',
        compute='_compute_monthly_subscription_amount',
        store=True,
        currency_field='currency_id',
    )
    odoo_modules = fields.Text(string='Odoo Modules Required')

    license_attachment_id = fields.Many2one('ir.attachment', string='Trade/Business License', copy=False)
    owner_document_attachment_id = fields.Many2one('ir.attachment', string='Owner Document', copy=False)
    license_uploaded_on = fields.Datetime(string='License Uploaded On', readonly=True, copy=False)
    owner_document_uploaded_on = fields.Datetime(string='Owner Document Uploaded On', readonly=True, copy=False)

    _sale_agreement_partner_year_company_uniq = models.Constraint(
        'unique(commercial_partner_id, agreement_year, company_id)',
        'Only one yearly agreement is allowed for this customer and year in the same company.',
    )

    @api.constrains('agreement_year')
    def _check_agreement_year(self):
        current_year = date.today().year
        for rec in self:
            if rec.agreement_year < 2000 or rec.agreement_year > current_year + 10:
                raise ValidationError(_('Agreement year is out of supported range.'))

    @api.constrains('license_attachment_id', 'owner_document_attachment_id')
    def _check_attachment_links(self):
        for rec in self:
            attachments = rec.license_attachment_id | rec.owner_document_attachment_id
            for attachment in attachments:
                if attachment and attachment.res_model and attachment.res_model != rec._name:
                    raise ValidationError(_('Uploaded documents must belong to the agreement record.'))
                if attachment and attachment.res_id and attachment.res_id != rec.id:
                    raise ValidationError(_('Uploaded documents must be linked to the current agreement record.'))

    @api.depends('sale_order_id.currency_id', 'company_id.currency_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.sale_order_id.currency_id or rec.company_id.currency_id

    @api.depends('sale_order_id.amount_total')
    def _compute_monthly_subscription_amount(self):
        for rec in self:
            rec.monthly_subscription_amount = rec.sale_order_id.amount_total or 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['partner_id'] = self._normalize_partner_id(vals.get('partner_id'))
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sale.agreement') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('partner_id'):
            vals['partner_id'] = self._normalize_partner_id(vals['partner_id'])
        return super().write(vals)

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_id = self.partner_id.commercial_partner_id

    def action_download_agreement_pdf(self):
        self.ensure_one()
        return self.env.ref('sale_agreement_report.action_report_yearly_sale_agreement').report_action(self)

    def action_replace_license(self, filename, file_bytes):
        self.ensure_one()
        attachment = self._create_validated_attachment(filename, file_bytes, 'License')
        if self.license_attachment_id:
            self.license_attachment_id.unlink()
        self.write({
            'license_attachment_id': attachment.id,
            'license_uploaded_on': fields.Datetime.now(),
        })

    def action_replace_owner_document(self, filename, file_bytes):
        self.ensure_one()
        attachment = self._create_validated_attachment(filename, file_bytes, 'Owner document')
        if self.owner_document_attachment_id:
            self.owner_document_attachment_id.unlink()
        self.write({
            'owner_document_attachment_id': attachment.id,
            'owner_document_uploaded_on': fields.Datetime.now(),
        })

    def _create_validated_attachment(self, filename, file_bytes, label):
        self.ensure_one()
        detected_type = self._validate_upload(filename, file_bytes, label)
        return self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(file_bytes).decode(),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': self._get_mimetype_for_type(detected_type),
        })

    @api.model
    def _validate_upload(self, filename, file_bytes, label):
        allowed_ext = {
            '.pdf': 'pdf',
            '.jpg': 'jpeg',
            '.jpeg': 'jpeg',
            '.png': 'png',
        }
        max_size = 10 * 1024 * 1024
        lower_name = (filename or '').lower()
        detected_type = self._detect_file_type(file_bytes)

        matching_extensions = [ext for ext in allowed_ext if lower_name.endswith(ext)]
        if not matching_extensions:
            raise ValidationError(_('%s must be PDF, JPG, or PNG.') % label)

        if not detected_type:
            raise ValidationError(_('%s file content is invalid or unsupported.') % label)

        if allowed_ext[matching_extensions[0]] != detected_type:
            raise ValidationError(_('%s file extension does not match the uploaded file content.') % label)

        if len(file_bytes) > max_size:
            raise ValidationError(_('%s exceeds maximum file size of 10 MB.') % label)

        return detected_type

    @api.model
    def _detect_file_type(self, file_bytes):
        if not file_bytes:
            return False
        if file_bytes.startswith(b'%PDF-'):
            return 'pdf'
        if file_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'png'
        if file_bytes[:3] == b'\xff\xd8\xff':
            return 'jpeg'
        return False

    @api.model
    def _get_mimetype_for_type(self, detected_type):
        if detected_type == 'pdf':
            return 'application/pdf'
        if detected_type == 'png':
            return 'image/png'
        return 'image/jpeg'

    def _get_modules_list(self):
        self.ensure_one()
        if self.odoo_modules:
            modules = self.odoo_modules.replace('\n', ',').split(',')
            return [module.strip() for module in modules if module.strip()]
        return []

    def _get_service_term_text(self):
        self.ensure_one()
        start_date = self.date_start or self.agreement_date or fields.Date.context_today(self)
        if self.date_end:
            return '%s to %s' % (start_date, self.date_end)
        return 'Commencing on %s and continuing on a recurring monthly basis until terminated in accordance with this Agreement.' % start_date
