# -*- coding: utf-8 -*-
"""Tag model – simple many2many for categorising documents"""

from odoo import api, fields, models

class SgcKnowledgeTag(models.Model):
    _name = 'sgc.knowledge.tag'
    _description = 'Tag for knowledge documents'

    name = fields.Char(string='Tag', required=True, index=True)
