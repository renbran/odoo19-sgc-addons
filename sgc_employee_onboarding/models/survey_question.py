"""Extend survey.question with a custom file upload question type."""
from odoo import fields, models


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    question_type = fields.Selection(
        selection_add=[('file_upload', 'File Upload')],
    )