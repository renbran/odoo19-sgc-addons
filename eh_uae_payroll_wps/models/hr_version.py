# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    wps_agent_id = fields.Char(
        string='WPS Agent ID (Bank Routing Code)',
        size=9,
        help='Bank routing code for WPS salary payments. Issued by the employer\'s bank.',
        groups='hr.group_hr_user',
    )
    wps_routing_code = fields.Char(
        string='WPS Routing Code',
        size=9,
        help='Additional routing code from employer\'s bank.',
        groups='hr.group_hr_user',
    )
    wps_employee_id = fields.Char(
        string='WPS Employee ID (Labor Card No)',
        size=14,
        related='employee_id.wps_employee_id',
        readonly=False,
        store=True,
        groups='hr.group_hr_user',
    )
    wps_iban = fields.Char(
        string='Salary IBAN',
        size=23,
        related='employee_id.wps_iban',
        readonly=False,
        store=True,
        groups='hr.group_hr_user',
    )