# -*- coding: utf-8 -*-
# Placeholder. Implemented in batch 3 (lead extensions for dashboard helpers).
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    dashboard_last_computed = fields.Datetime('Dashboard Last Computed')
