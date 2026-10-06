# -*- coding: utf-8 -*-
from odoo import fields, models


class ConstructionProjectPhoto(models.Model):
    _name = 'construction.project.photo'
    _description = 'Construction Project Site Photo'
    _order = 'date desc, id desc'

    project_id = fields.Many2one('construction.project', required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Caption', default='Site Photo')
    image_1920 = fields.Image(string='Photo', max_width=1920, max_height=1920, required=True)
    image_128 = fields.Image(string='Thumbnail', related='image_1920', max_width=128, max_height=128, store=True)
    date = fields.Date(string='Date Taken', default=fields.Date.today)
    taken_by_id = fields.Many2one('res.users', string='Taken By', default=lambda self: self.env.user)
