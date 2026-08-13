"""Hook the public survey submission to auto-populate the employee record."""
from odoo import models


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def _mark_done(self):
        res = super()._mark_done()
        for user_input in self:
            if user_input.state != 'done' or user_input.test_entry:
                continue
            employee = self.env['hr.employee'].sudo().search([
                ('onboarding_survey_id', '=', user_input.survey_id.id),
            ], limit=1)
            if employee:
                employee._process_survey_submission(user_input)
        return res