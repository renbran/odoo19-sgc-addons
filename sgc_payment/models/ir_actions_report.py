# -*- coding: utf-8 -*-

from odoo import models
import logging
import os

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _get_wkhtmltopdf_command(self, paperformat, landscape, specific_paperformat_args=None, set_viewport_size=False):
        """Override to add SSL-safe options and error handling"""
        command = super()._get_wkhtmltopdf_command(
            paperformat, landscape, specific_paperformat_args, set_viewport_size
        )
        
        # Add SSL-safe options to prevent empty PDF errors
        ssl_safe_options = [
            '--load-error-handling', 'ignore',
            '--load-media-error-handling', 'ignore',
            '--javascript-delay', '1000',
            '--no-stop-slow-scripts',
        ]
        
        # Insert SSL-safe options before the output file parameter
        if len(command) >= 2:
            # Insert before the last two arguments (input and output)
            insert_position = len(command) - 2
            for i, option in enumerate(ssl_safe_options):
                command.insert(insert_position + i, option)
        
        return command

    def _run_wkhtmltopdf(self, bodies, **kwargs):
        """Override to add environment variables for better PDF generation"""
        # Set environment variables for Qt/SSL issues
        env = os.environ.copy()
        env.update({
            'QT_QPA_PLATFORM': 'offscreen',
            'QTWEBKIT_DPI': '96',
            'QT_QPA_FONTDIR': '/usr/share/fonts',
        })
        
        # Apply environment and use standard Odoo PDF generation
        original_env = os.environ.copy()
        try:
            os.environ.update(env)
            return super()._run_wkhtmltopdf(bodies, **kwargs)
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
