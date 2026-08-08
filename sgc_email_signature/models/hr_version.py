from odoo import api, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('employee_id')._update_email_signature()
        return records

    def write(self, vals):
        res = super().write(vals)
        tracked = {'job_title', 'name', 'department_id', 'contract_date_start', 'company_id'}
        if tracked.intersection(vals):
            self.mapped('employee_id')._update_email_signature()
        return res