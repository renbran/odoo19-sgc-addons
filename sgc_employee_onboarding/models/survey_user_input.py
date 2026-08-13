"""Hook the public survey submission to auto-populate the employee record."""
from odoo import _, models
from odoo.exceptions import UserError


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        if question.question_type == 'file_upload':
            return self._save_line_file_upload(question, answer, overwrite_existing)
        return super()._save_lines(
            question, answer, comment=comment, overwrite_existing=overwrite_existing)

    def _save_line_file_upload(self, question, answer, overwrite_existing=True):
        old_answers = self.env['survey.user_input.line'].search([
            ('user_input_id', '=', self.id),
            ('question_id', '=', question.id)
        ])
        if old_answers and not overwrite_existing:
            raise UserError(_("This answer cannot be overwritten."))

        vals = {
            'user_input_id': self.id,
            'question_id': question.id,
            'skipped': False,
            'answer_type': 'file_upload',
        }
        attachment_id = False
        if answer and str(answer).strip().isdigit():
            attachment = self.env['ir.attachment'].sudo().search([
                ('id', '=', int(answer)),
                ('res_model', '=', 'survey.user_input'),
                ('res_id', '=', self.id),
            ], limit=1)
            if attachment:
                attachment_id = attachment.id

        if not attachment_id:
            vals.update(answer_type=None, skipped=True)
        else:
            vals['answer_attachment_ids'] = [(6, 0, [attachment_id])]

        if old_answers:
            old_answers.write(vals)
            return old_answers
        return self.env['survey.user_input.line'].create(vals)

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