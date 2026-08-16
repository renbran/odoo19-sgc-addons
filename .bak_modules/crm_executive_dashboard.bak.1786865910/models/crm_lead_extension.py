# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    dashboard_last_computed = fields.Datetime('Dashboard Last Computed')
    last_redistribution_date = fields.Datetime(
        string='Last Redistribution Date',
        help='Timestamp of last redistribution to a new owner',
        copy=False,
    )
