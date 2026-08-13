"""Extend survey.user_input.line to store uploaded files for file_upload questions."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    @api.constrains('skipped', 'answer_type')
    def _check_answer_type_skipped(self):
        # given/when: file_upload lines store the answer in answer_attachment_ids,
        # not in a value_* field (which would be 'value_file_upload' and does not exist)
        for line in self.filtered(lambda l: l.answer_type == 'file_upload'):
            if line.skipped == bool(line.answer_type):
                raise ValidationError(
                    _('A question can either be skipped or answered, not both.'))
            if not line.skipped and not line.answer_attachment_ids:
                raise ValidationError(_('The answer must be in the right type'))
        other_lines = self.filtered(lambda l: l.answer_type != 'file_upload')
        if other_lines:
            super(SurveyUserInputLine, other_lines)._check_answer_type_skipped()