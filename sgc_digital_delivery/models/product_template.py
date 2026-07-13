# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Hard limit for digital file uploads (50 MB unencoded)
_MAX_FILE_BYTES = 50 * 1024 * 1024


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_digital = fields.Boolean(
        string='Digital Product',
        default=False,
        help='Enable to attach a downloadable file. '
             'Buyers receive a secure download link by email after payment.',
    )
    digital_file = fields.Binary(
        string='Digital File',
        attachment=True,
        copy=False,
        groups='product.group_product_manager',
        help='Upload the file (ZIP, PDF, etc.) to deliver after payment. Max 50 MB.',
    )
    digital_filename = fields.Char(
        string='File Name',
        default='download.zip',
        copy=False,
        help='Filename the buyer sees when downloading (e.g. my-product-v1.zip).',
    )
    digital_download_count = fields.Integer(
        string='Times Delivered',
        default=0,
        readonly=True,
        copy=False,
        help='Number of times the download link has been accessed by buyers.',
    )

    # ── Validation ────────────────────────────────────────────────────────────

    @api.constrains('digital_file')
    def _check_digital_file_size(self):
        """Reject uploads larger than _MAX_FILE_BYTES to protect the mail server."""
        for rec in self:
            if rec.digital_file:
                try:
                    size = len(base64.b64decode(rec.digital_file))
                except Exception:
                    raise ValidationError(
                        _('Digital File: the uploaded data is not valid base64.')
                    )
                if size > _MAX_FILE_BYTES:
                    raise ValidationError(
                        _('Digital File: file exceeds the 50 MB limit (%(size).1f MB uploaded). '
                          'Use a file hosting service and share a link instead.') % {
                            'size': size / 1024 / 1024}
                    )

    @api.constrains('is_digital', 'digital_filename')
    def _check_digital_filename(self):
        """Ensure a filename is set whenever a product is marked digital."""
        for rec in self:
            if rec.is_digital and not rec.digital_filename:
                raise ValidationError(
                    _('Digital Products require a File Name (e.g. download.zip).')
                )

    # NOTE: No _sql_constraints / models.Constraint here — adding a CHECK
    # on the shared product_template table is fragile during upgrades and is
    # already enforced at ORM level by _check_digital_filename above.

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._sync_attachment_filename()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'digital_filename' in vals or 'digital_file' in vals:
            for rec in self:
                rec._sync_attachment_filename()
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sync_attachment_filename(self):
        """Keep the underlying ir.attachment name in sync with digital_filename
        so the correct filename appears in emails and download responses."""
        for rec in self:
            if not (rec.digital_file and rec.digital_filename):
                continue
            att = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'product.template'),
                ('res_field', '=', 'digital_file'),
                ('res_id', '=', rec.id),
            ], limit=1)
            if att and att.name != rec.digital_filename:
                att.sudo().write({'name': rec.digital_filename})

    def _get_digital_attachment(self):
        """Return the ir.attachment for this product's digital_file, or None."""
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'product.template'),
            ('res_field', '=', 'digital_file'),
            ('res_id', '=', self.id),
        ], limit=1)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Expose on variant level so website templates and order lines can use it
    is_digital = fields.Boolean(
        related='product_tmpl_id.is_digital',
        store=True,
        string='Digital Product',
    )

