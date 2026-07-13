# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ConstructionSiteDiary(models.Model):
    _name = 'construction.site.diary'
    _description = 'Site Diary'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    project_id = fields.Many2one('construction.project', string='Project', required=True, index=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    weather = fields.Selection([
        ('sunny', 'Sunny'),
        ('cloudy', 'Cloudy'),
        ('rain', 'Rain'),
        ('high_wind', 'High Wind'),
        ('dust', 'Dust/Sandstorm'),
        ('extreme_heat', 'Extreme Heat'),
    ], default='sunny', tracking=True)
    temperature = fields.Float('Temp (°C)')
    shift = fields.Selection([
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('double', 'Double Shift'),
    ], default='day')
    prepared_by = fields.Many2one('res.users', string='Prepared By', default=lambda self: self.env.user)

    labor_summary_ids = fields.One2many('construction.site.diary.labor', 'diary_id', string='Labor Summary')
    equipment_summary_ids = fields.One2many('construction.site.diary.equipment', 'diary_id', string='Equipment Summary')
    activity_ids = fields.One2many('construction.site.diary.activity', 'diary_id', string='Activities')
    material_ids = fields.One2many('construction.site.diary.material', 'diary_id', string='Materials')
    issue_ids = fields.One2many('construction.site.diary.issue', 'diary_id', string='Issues/Delays')
    photo_ids = fields.Many2many('ir.attachment', string='Progress Photos')
    remarks = fields.Text()

class ConstructionSiteDiaryLabor(models.Model):
    _name = 'construction.site.diary.labor'
    _description = 'Site Diary Labor'

    diary_id = fields.Many2one('construction.site.diary', ondelete='cascade')
    trade = fields.Char('Trade/Skill', required=True)
    contractor_id = fields.Many2one('res.partner', string='Contractor/Subcontractor')
    planned_qty = fields.Integer('Planned')
    actual_qty = fields.Integer('Actual')

class ConstructionSiteDiaryEquipment(models.Model):
    _name = 'construction.site.diary.equipment'
    _description = 'Site Diary Equipment'

    diary_id = fields.Many2one('construction.site.diary', ondelete='cascade')
    equipment_id = fields.Many2one('construction.equipment', string='Equipment')
    name = fields.Char('Equipment Name')
    hours_utilized = fields.Float('Hours')
    status = fields.Selection([
        ('working', 'Working'),
        ('idle', 'Idle'),
        ('breakdown', 'Breakdown'),
    ], default='working')

class ConstructionSiteDiaryActivity(models.Model):
    _name = 'construction.site.diary.activity'
    _description = 'Site Diary Activity'

    diary_id = fields.Many2one('construction.site.diary', ondelete='cascade')
    wbs_id = fields.Many2one('construction.wbs', string='WBS Phase')
    description = fields.Text('Activity Description', required=True)
    progress_percent = fields.Float('Progress %')

class ConstructionSiteDiaryMaterial(models.Model):
    _name = 'construction.site.diary.material'
    _description = 'Site Diary Material'

    diary_id = fields.Many2one('construction.site.diary', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Material')
    uom_id = fields.Many2one('uom.uom', string='UOM')
    qty_received = fields.Float('Received')
    qty_consumed = fields.Float('Consumed')

class ConstructionSiteDiaryIssue(models.Model):
    _name = 'construction.site.diary.issue'
    _description = 'Site Diary Issue'

    diary_id = fields.Many2one('construction.site.diary', ondelete='cascade')
    issue_type = fields.Selection([
        ('material', 'Material Delay'),
        ('labor', 'Labor Shortage'),
        ('equipment', 'Equipment Failure'),
        ('weather', 'Weather Delay'),
        ('design', 'Design/RFI Delay'),
        ('other', 'Other'),
    ], default='other')
    description = fields.Text('Description', required=True)
    impact_hours = fields.Float('Impact (Hours)')

class ConstructionEquipment(models.Model):
    _name = 'construction.equipment'
    _description = 'Construction Equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    code = fields.Char('Equipment Code', copy=False)
    category = fields.Selection([
        ('heavy', 'Heavy Equipment'),
        ('light', 'Light Equipment'),
        ('tools', 'Tools'),
        ('vehicle', 'Vehicle'),
    ], default='heavy')
    status = fields.Selection([
        ('operational', 'Operational'),
        ('maintenance', 'Under Maintenance'),
        ('breakdown', 'Breakdown'),
        ('idle', 'Idle'),
    ], default='operational', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

class ConstructionEquipmentLog(models.Model):
    _name = 'construction.equipment.log'
    _description = 'Equipment Utilization Log'
    _order = 'date desc'

    equipment_id = fields.Many2one('construction.equipment', required=True)
    project_id = fields.Many2one('construction.project', required=True)
    date = fields.Date(default=fields.Date.context_today)
    hours_utilized = fields.Float('Hours Utilized')
    fuel_consumed = fields.Float('Fuel Consumed (L)')
    remarks = fields.Text()

class ConstructionLaborAttendance(models.Model):
    _name = 'construction.labor.attendance'
    _description = 'Labor Attendance'
    _order = 'date desc'

    project_id = fields.Many2one('construction.project', required=True)
    date = fields.Date(default=fields.Date.context_today)
    employee_id = fields.Many2one('res.partner', string='Worker', domain="[('is_company', '=', False)]")
    trade = fields.Char('Trade')
    hours = fields.Float('Regular Hours')
    overtime = fields.Float('Overtime Hours')
    remarks = fields.Text()
