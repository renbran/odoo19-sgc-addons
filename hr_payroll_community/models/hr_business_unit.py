# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import api, fields, models


class HrBusinessUnit(models.Model):
    """Hr Business Unit for organizational structure"""
    _name = 'hr.business.unit'
    _description = 'Business Unit'
    _order = 'code, name'

    name = fields.Char(string='Business Unit Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, size=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company.id
    )
    active = fields.Boolean(default=True, string='Active')
    description = fields.Text(string='Description')
    
    # Hierarchy
    parent_id = fields.Many2one(
        'hr.business.unit',
        string='Parent Business Unit',
        index=True
    )
    child_ids = fields.One2many(
        'hr.business.unit',
        'parent_id',
        string='Child Business Units'
    )
    
    # Manager
    manager_id = fields.Many2one(
        'res.users',
        string='Unit Manager',
        help='The user who manages this business unit'
    )
    
    # Employees
    employee_ids = fields.One2many(
        'hr.employee',
        'business_unit_id',
        string='Employees'
    )
    employee_count = fields.Integer(
        compute='_compute_employee_count',
        string='Employee Count'
    )

    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for unit in self:
            unit.employee_count = len(unit.employee_ids)

    def name_get(self):
        result = []
        for unit in self:
            name = f'{unit.code} - {unit.name}' if unit.code else unit.name
            result.append((unit.id, name))
        return result