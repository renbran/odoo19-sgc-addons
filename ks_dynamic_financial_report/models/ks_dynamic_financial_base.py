# -*- coding: utf-8 -*-
from odoo import models, fields


class KsDynamicFinancialBase(models.Model):
    """Base model for dynamic financial reports"""
    _name = 'ks.dynamic.financial.base'
    _description = 'Dynamic Financial Report Base'
    
    ks_name = fields.Char(string='Name')
    ks_parent_id = fields.Many2one('ks.dynamic.financial.base', string='Parent')
    ks_level = fields.Integer(string='Level', compute='_compute_level', store=False)
    ks_sequence = fields.Integer(string='Sequence')
    
    def _compute_level(self):
        """Compute the level in the hierarchy"""
        for record in self:
            level = 0
            parent = record.ks_parent_id
            while parent:
                level += 1
                parent = parent.ks_parent_id
            record.ks_level = level
