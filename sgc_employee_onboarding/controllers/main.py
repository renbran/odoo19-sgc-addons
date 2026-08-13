"""Public endpoint that receives file uploads for survey file_upload questions."""
import base64
import json

from odoo import http
from odoo.http import Response, request

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


class SgcOnboardingSurveyUpload(http.Controller):

    @http.route('/sgc_onboarding/survey/upload_file', type='http', auth='public',
                methods=['POST'], csrf=True)
    def upload_survey_file(self, ufile=None, question_id=None, answer_token=None, **kw):
        # The answer must exist and still be editable (not yet fully submitted)
        answer = request.env['survey.user_input'].sudo().search(
            [('access_token', '=', answer_token or '')], limit=1)
        if not answer:
            return self._json({'error': 'Invalid survey token.'})
        if answer.state == 'done':
            return self._json({'error': 'This survey has already been submitted.'})

        # The question must belong to that survey and be a file_upload type
        try:
            question = request.env['survey.question'].sudo().browse(int(question_id))
        except (TypeError, ValueError):
            question = request.env['survey.question']
        if (not question.exists()
                or question.question_type != 'file_upload'
                or question.survey_id.id != answer.survey_id.id):
            return self._json({'error': 'Invalid question.'})

        # Validate the uploaded file
        if not ufile or not getattr(ufile, 'filename', ''):
            return self._json({'error': 'No file provided.'})
        data = ufile.read()
        if not data:
            return self._json({'error': 'The file is empty.'})
        if len(data) > MAX_UPLOAD_BYTES:
            return self._json({'error': 'The file exceeds the 25 MB size limit.'})

        attachment = request.env['ir.attachment'].sudo().create({
            'name': ufile.filename,
            'datas': base64.b64encode(data),
            'mimetype': ufile.mimetype or 'application/octet-stream',
            'res_model': 'survey.user_input',
            'res_id': answer.id,
            'type': 'binary',
        })
        return self._json({'attachment_id': attachment.id, 'name': attachment.name})

    def _json(self, payload):
        return Response(json.dumps(payload), mimetype='application/json')