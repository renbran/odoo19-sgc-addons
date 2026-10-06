import base64
import logging

from odoo import api, fields, models, tools

from ..services.resume_parser import process_attachment

_logger = logging.getLogger(__name__)

RECRUITMENT_EMAILS = [
    'hiring@sgctech.ai',
    'recruitment@sgctech.ai',
]
DEFAULT_JOB_ID = 1
RESUME_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.rtf', '.html', '.htm'}


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    candidate_skills = fields.Text('Skills')
    candidate_experience = fields.Text('Professional Experience')
    candidate_education = fields.Text('Education')
    candidate_certifications = fields.Text('Certifications')
    candidate_current_role = fields.Char('Current Job Title')
    candidate_current_company = fields.Char('Current Company')
    candidate_experience_years = fields.Float('Years of Experience')
    candidate_availability = fields.Char('Availability')

    def _get_resume_attachment(self):
        """Find the first resume attachment for this applicant."""
        self.ensure_one()
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', 'hr.applicant'),
            ('res_id', '=', self.id),
        ], order='create_date desc')
        for att in attachments:
            if att.name and any(att.name.lower().endswith(ext) for ext in RESUME_EXTENSIONS):
                return att
        return False

    def action_parse_resume(self):
        """Manually parse the first resume attachment for this applicant."""
        self.ensure_one()
        attachment = self._get_resume_attachment()
        if not attachment:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Resume Found',
                    'message': 'No resume attachment (PDF, DOCX, TXT) found for this applicant.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        try:
            content_b64 = base64.b64encode(attachment.raw).decode() if attachment.raw else base64.b64encode(attachment.datas).decode()
            mime = attachment.mimetype or ''
            process_attachment(self.env, self.id, (attachment.name, content_b64, mime))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Resume Parsed',
                    'message': f'Successfully parsed resume: {attachment.name}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error('Manual resume parse failed for applicant %s: %s', self.id, e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Parse Failed',
                    'message': f'Error parsing resume: {str(e)}',
                    'type': 'danger',
                    'sticky': False,
                }
            }

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        to_field = (msg_dict.get('to') or '') + ' ' + (msg_dict.get('cc') or '')
        to_lower = to_field.lower()

        if any(email in to_lower for email in RECRUITMENT_EMAILS):
            if not custom_values:
                custom_values = {}
            if 'job_id' not in custom_values:
                custom_values['job_id'] = DEFAULT_JOB_ID
                _logger.info(
                    'Assigned job_id=%s for applicant from %s (recipient matched: %s)',
                    DEFAULT_JOB_ID, msg_dict.get('from'), to_field.strip()
                )

        applicant_id = super().message_new(msg_dict, custom_values=custom_values)

        # Process first resume attachment asynchronously
        attachments = msg_dict.get('attachments') or []
        for att in attachments:
            name = att[0] if isinstance(att, (list, tuple)) and len(att) > 0 else ''
            if any(name.lower().endswith(ext) for ext in RESUME_EXTENSIONS):
                content_bytes = att[1] if isinstance(att, (list, tuple)) and len(att) > 1 else b''
                mime = att[2] if isinstance(att, (list, tuple)) and len(att) > 2 else ''
                if not content_bytes:
                    continue
                content_b64 = base64.b64encode(content_bytes).decode()
                self.env.cr.commit()
                process_attachment(
                    self.env, applicant_id,
                    (name, content_b64, mime)
                )
                break

        return applicant_id
