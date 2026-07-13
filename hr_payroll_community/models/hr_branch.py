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
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrBranch(models.Model):
    """Hr Branch for managing multiple office locations"""
    _name = 'hr.branch'
    _description = 'Branch'
    _order = 'code, name'

    name = fields.Char(string='Branch Name', required=True, translate=True)
    code = fields.Char(string='Branch Code', required=True, size=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company.id
    )
    active = fields.Boolean(default=True, string='Active')
    description = fields.Text(string='Description')
    
    # Address fields
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State')
    country_id = fields.Many2one('res.country', string='Country')
    zip = fields.Char(string='Zip', size=10)
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    website = fields.Char(string='Website')
    
    # Manager
    manager_id = fields.Many2one(
        'res.users',
        string='Branch Manager',
        help='The user who manages this branch'
    )
    
    # Relations
    department_ids = fields.One2many(
        'hr.department',
        'branch_id',
        string='Departments'
    )
    employee_count = fields.Integer(
        compute='_compute_employee_count',
        string='Employees'
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code, company_id)', 
         'Branch code must be unique per company!'),
    ]

    @api.depends('department_ids')
    def _compute_employee_count(self):
        for branch in self:
            branch.employee_count = len(branch.department_ids.mapped('employee_ids'))

    def name_get(self):
        result = []
        for branch in self:
            name = f'{branch.code} - {branch.name}' if branch.code else branch.name
            result.append((branch.id, name))
        return result