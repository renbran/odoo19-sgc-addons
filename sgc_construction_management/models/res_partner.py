# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_export_soa_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/sgc_construction_management/xlsx/soa/%s' % self.id,
            'target': 'self',
        }
