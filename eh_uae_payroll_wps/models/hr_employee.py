# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    wps_employee_id = fields.Char(
        string='WPS Employee ID (Labor Card No)',
        size=14,
        help='UAE MOHRE Labor Card Number. Required for WPS file generation.',
        groups='hr.group_hr_user',
    )
    wps_iban = fields.Char(
        string='Salary IBAN',
        size=23,
        help='International Bank Account Number for salary payment (AE + 21 digits).',
        groups='hr.group_hr_user',
    )
    wps_bank_id = fields.Many2one(
        'res.bank',
        string='Salary Bank',
        groups='hr.group_hr_user',
    )
    wps_nationality_id = fields.Many2one(
        'res.country',
        string='Nationality',
        groups='hr.group_hr_user',
    )
    wps_passport_no = fields.Char(
        string='Passport Number',
        size=20,
        groups='hr.group_hr_user',
    )