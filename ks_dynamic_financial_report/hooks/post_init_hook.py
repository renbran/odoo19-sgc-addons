# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Post-installation hook for ks_dynamic_financial_report module."""
from odoo import api, SUPERUSER_ID


def post_init_hook(cr, registry):
    """Post-init hook for module installation/upgrade to Odoo 19.
    
    Args:
        cr: Database cursor
        registry: Odoo registry instance
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Ensure financial report models are initialized
    env['ks.dynamic.financial.reports'].search([], limit=1)
    
    # Clear cache for data consistency
    registry.clear_cache()
