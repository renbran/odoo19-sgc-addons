# -*- coding: utf-8 -*-
# Placeholder. Implemented in batch 3 (team extensions).
from odoo import fields, models


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    dashboard_target_revenue = fields.Monetary('Monthly Revenue Target')
