# -*- coding: utf-8 -*-

from odoo import models, fields, api
import os


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pdf_generation_mode = fields.Selection([
        ('standard', 'Standard PDF Generation'),
        ('ssl_safe', 'SSL-Safe PDF Generation (Recommended)'),
        ('fallback', 'Fallback Mode (Most Compatible)')
    ], string='PDF Generation Mode', default='ssl_safe',
        help="Choose PDF generation mode to handle SSL and network issues")

    @api.model
    def set_values(self):
        super().set_values()
        # Set environment variables based on configuration
        if self.pdf_generation_mode in ['ssl_safe', 'fallback']:
            # Set Qt environment variables for better PDF generation
            os.environ.update({
                'QT_QPA_PLATFORM': 'offscreen',
                'QTWEBKIT_DPI': '96',
                'QT_QPA_FONTDIR': '/usr/share/fonts',
            })

    @api.model
    def get_values(self):
        res = super().get_values()
        config_param = self.env['ir.config_parameter'].sudo()
        res.update({
            'pdf_generation_mode': config_param.get_param('payment_account_enhanced.pdf_generation_mode', 'ssl_safe'),
        })
        return res

    def set_values(self):
        super().set_values()
        config_param = self.env['ir.config_parameter'].sudo()
        config_param.set_param('payment_account_enhanced.pdf_generation_mode', self.pdf_generation_mode)
