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


class HrJob(models.Model):
    """Hr Job Position"""
    _name = 'hr.job'
    _description = 'Job Position'
    _order = 'sequence, name'

    name = fields.Char(string='Job Title', required=True, translate=True)
    code = fields.Char(string='Job Code', size=10)
    sequence = fields.Integer(string='Sequence', default=10)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company.id
    )
    active = fields.Boolean(default=True, string='Active')
    description = fields.Text(string='Description')
    requirements = fields.Text(string='Requirements')
    
    # Grade and Level
    job_grade_id = fields.Many2one(
        'hr.job.grade',
        string='Job Grade'
    )
    job_level_id = fields.Many2one(
        'hr.job.level',
        string='Job Level'
    )
    
    # Department
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        help='Primary department for this position'
    )
    
    # Employment Type
    employment_type_id = fields.Many2one(
        'hr.employment.type',
        string='Employment Type'
    )
    
    # Contract Template
    contract_template_id = fields.Many2one(
        'hr.contract.advantage.template',
        string='Contract Template',
        help='Contract template to use when creating contracts for this position'
    )
    
    # Payroll Structure
    struct_id = fields.Many2one(
        'hr.payroll.structure',
        string='Salary Structure',
        help='Default salary structure for this position'
    )
    
    # Requirements
    no_of_recruitment = fields.Integer(
        string='Expected New Employees',
        default=1,
        help='Number of employees to recruit for this position'
    )
    no_of_employee = fields.Integer(
        compute='_compute_employee_count',
        string='Current Employees'
    )
    
    # Skills
    skill_ids = fields.Many2many(
        'hr.skill',
        'hr_job_skill_rel',
        'job_id',
        'skill_id',
        string='Required Skills'
    )

    @api.depends('department_id.employee_ids')
    def _compute_employee_count(self):
        for job in self:
            job.no_of_employee = len(
                job.department_id.employee_ids.filtered(
                    lambda e: e.job_id == job and e.active
                )
            )