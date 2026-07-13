# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Uninstall hook for ks_dynamic_financial_report module."""
from odoo import api, SUPERUSER_ID


def uninstall_hook(cr, registry):
    """Hook to execute on module uninstall.
    
    Args:
        cr: Database cursor
        registry: Odoo registry instance
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Clean up module-specific configurations
    registry.clear_cache()
