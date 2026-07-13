# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sgc_website_booking_type_id = fields.Many2one(
        comodel_name='resource.booking.type',
        string='Public Booking Type',
        config_parameter='sgc_website_booking.type_id',
        help='Booking type offered on the public /book-session page. Its '
             'working-hours calendar, slot duration and meeting provider drive '
             'the slots shown to website visitors.',
    )
