"""Extend survey.user_input.line to store uploaded files for file_upload questions."""
from odoo import api, fields, models, _


class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    answer_type = fields.Selection(
        selection_add=[('file_upload', 'File Upload')],
    )

    answer_attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Uploaded Files',
        help='Attachments uploaded by the respondent for file_upload questions.',
    )

    @api.depends('answer_type', 'answer_attachment_ids',
                 'value_text_box', 'value_numerical_box',
                 'value_char_box', 'value_date', 'value_datetime',
                 'suggested_answer_id.value', 'matrix_row_id.value')
    def _compute_display_name(self):
        super()._compute_display_name()
        for line in self.filtered(lambda l: l.answer_type == 'file_upload'):
            attachment = line.answer_attachment_ids[:1]
            line.display_name = attachment.name if attachment else _('Skipped')