# -*- coding: utf-8 -*-
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Identity fields not provided by Odoo 19 core (passport/visa expiry live on hr.version)
    visa_number = fields.Char(string="Visa Number", groups="hr.group_hr_user", tracking=True)
    visa_type = fields.Char(string="Visa Type", groups="hr.group_hr_user", tracking=True)

    # Onboarding survey fields
    onboarding_survey_id = fields.Many2one(
        'survey.survey',
        string='Onboarding Survey',
        help='Survey used for this employee\'s onboarding'
    )

    onboarding_survey_link = fields.Char(
        string='Onboarding Survey Link',
        compute='_compute_onboarding_survey_link',
        help='Public link for the employee to complete their onboarding survey'
    )

    onboarding_survey_deadline = fields.Date(
        string='Survey Deadline',
        help='Date by which the employee should complete the onboarding survey'
    )

    onboarding_last_submitted = fields.Datetime(
        string='Last Submission Date',
        help='When the employee last submitted their onboarding survey'
    )

    onboarding_last_user_input_id = fields.Many2one(
        'survey.user_input',
        string='Last Survey Submission',
        readonly=True,
        help='Technical field used to avoid processing the same submission twice'
    )

    onboarding_state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('expired', 'Expired')
    ], string='Onboarding Status', default='not_started', compute='_compute_onboarding_state', store=True)

    @api.depends('onboarding_survey_id', 'onboarding_survey_deadline')
    def _compute_onboarding_survey_link(self):
        """Generate the public survey link for this employee"""
        for employee in self:
            survey = employee.onboarding_survey_id
            if survey and survey.access_token:
                employee.onboarding_survey_link = "%s/survey/start/%s" % (
                    employee.get_base_url(), survey.access_token)
            else:
                employee.onboarding_survey_link = False

    @api.depends('onboarding_survey_deadline', 'onboarding_last_submitted', 'onboarding_state')
    def _compute_onboarding_state(self):
        """Compute the onboarding status based on deadline and submission"""
        for employee in self:
            if not employee.onboarding_survey_id:
                employee.onboarding_state = 'not_started'
                continue
            if employee.onboarding_survey_deadline and \
                    employee.onboarding_survey_deadline < fields.Date.context_today(employee):
                employee.onboarding_state = 'expired'
                continue
            if employee.onboarding_last_submitted:
                employee.onboarding_state = 'completed'
                continue
            employee.onboarding_state = 'in_progress'

    def action_generate_onboarding_survey(self):
        """Generate or regenerate the onboarding survey for this employee"""
        self.ensure_one()

        survey_template = self._get_default_onboarding_survey_template()
        if not survey_template:
            raise ValidationError(_("No onboarding survey template available. Please configure one first."))

        survey_copy = survey_template.copy({
            'title': '%s - %s' % (survey_template.title, self.name),
            'access_token': False,
            'access_mode': 'public',
            'users_login_required': False,
            'scoring_type': 'no_scoring',
        })
        # Mint a fresh public access token for this employee's copy
        survey_copy.access_token = survey_copy._get_default_access_token()

        self.onboarding_survey_id = survey_copy.id
        self.onboarding_state = 'in_progress'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Onboarding Survey Generated'),
                'message': _('Onboarding survey link has been generated for %s') % self.name,
                'type': 'success',
                'sticky': True,
            }
        }

    def action_send_onboarding_survey(self):
        """Send the onboarding survey link to the employee via email"""
        self.ensure_one()
        if not self.work_email:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No email on employee'),
                    'message': _('Add a work email address to the employee before sending the survey link.'),
                    'type': 'warning',
                    'sticky': True,
                },
            }

        if not self.onboarding_survey_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No survey assigned'),
                    'message': _('Please generate an onboarding survey first.'),
                    'type': 'warning',
                    'sticky': True,
                },
            }

        template = self.env.ref('sgc_employee_onboarding.email_template_employee_onboarding',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=False)
            self.message_post(
                body=_('Onboarding survey link e-mailed to %(email)s.') % {'email': self.work_email},
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        else:
            self.message_post(
                body=_('Please send the onboarding survey link manually: %s') % self.onboarding_survey_link,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Link Sent'),
                'message': _('Onboarding survey link sent to %s') % self.work_email,
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_default_onboarding_survey_template(self):
        """Get the default onboarding survey template (created by the data file)"""
        return self.env['survey.survey'].search([
            ('title', '=', 'SGC Employee Onboarding Survey'),
        ], limit=1)

    def _create_default_onboarding_survey_template(self):
        """Legacy entry point; the template is provided by the module data file"""
        return self._get_default_onboarding_survey_template()

    def _process_survey_submission(self, survey_user_input):
        """Process a completed survey: map answers onto the employee record."""
        self.ensure_one()
        if not survey_user_input or survey_user_input.state != 'done' or survey_user_input.test_entry:
            return False
        # Idempotency guard: never process the same submission twice
        if self.onboarding_last_user_input_id.id == survey_user_input.id:
            return True

        lines = survey_user_input.user_input_line_ids.filtered(lambda line: not line.skipped)
        answers_by_question = {}
        for line in lines:
            answers_by_question.setdefault(line.question_id.id, []).append(line)

        vals = {}
        for question_id, question_lines in answers_by_question.items():
            question = self.env['survey.question'].browse(question_id)
            answer_value = self._extract_answer_value(
                question, self.env['survey.user.input.line'].concat(question_lines))
            if answer_value is None:
                continue
            mapped = self._map_question_to_employee_field(question, answer_value)
            if mapped:
                vals.update(mapped)

        employee = self.sudo()
        if vals:
            employee.write(vals)
        employee.write({
            'onboarding_last_submitted': fields.Datetime.now(),
            'onboarding_last_user_input_id': survey_user_input.id,
            'onboarding_state': 'completed',
        })
        employee.message_post(
            body=_('Employee %s has completed their onboarding survey.') % self.name,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        return True

    @api.model
    def _extract_answer_value(self, question, lines):
        """Extract the answer(s) for a question from its input lines (Odoo 19 answer_type)."""
        qtype = question.question_type
        if qtype in ('simple_choice', 'multiple_choice'):
            answers = [
                line.suggested_answer_id.value
                for line in lines
                if line.answer_type == 'suggestion' and line.suggested_answer_id
            ]
            if qtype == 'multiple_choice':
                return answers or None
            return answers[0] if answers else None
        if qtype == 'char_box':
            lines = lines.filtered('value_char_box')
            return lines[0].value_char_box if lines else None
        if qtype == 'text_box':
            lines = lines.filtered('value_text_box')
            return lines[0].value_text_box if lines else None
        if qtype == 'numerical_box':
            lines = lines.filtered(lambda line: line.value_numerical_box is not False)
            return lines[0].value_numerical_box if lines else None
        if qtype == 'date':
            lines = lines.filtered('value_date')
            return lines[0].value_date if lines else None
        if qtype == 'datetime':
            lines = lines.filtered('value_datetime')
            return lines[0].value_datetime if lines else None
        return None

    def _map_question_to_employee_field(self, question, answer_value):
        """Return the {field: value} dict to write on the employee, or {} if unmapped."""
        title = (question.title or '').strip().lower()
        if not title or answer_value is None:
            return {}

        # Direct char fields
        simple_mappings = {
            'work email': ('work_email', str),
            'personal email': ('private_email', str),
            'work phone': ('work_phone', str),
            'mobile phone': ('mobile_phone', str),
            'home phone': ('private_phone', str),
            'emergency contact': ('emergency_contact', str),
            'emergency phone': ('emergency_phone', str),
            'job position': ('job_title', str),
            'passport number': ('passport_id', str),
            'visa number': ('visa_number', str),
            'visa type': ('visa_type', str),
        }
        for pattern, (field_name, converter) in simple_mappings.items():
            if pattern in title:
                return {field_name: converter(answer_value).strip()}

        # Date fields
        if 'date of birth' in title:
            return {'birthday': answer_value} if isinstance(answer_value, date) else {}
        if 'visa expiration' in title:
            return {'visa_expire': answer_value} if isinstance(answer_value, date) else {}

        # Numeric field
        if 'number of dependent children' in title or 'number of children' in title:
            try:
                return {'children': int(float(answer_value))}
            except (TypeError, ValueError):
                return {}

        # Selection fields (answer value is the suggested answer label)
        if 'marital status' in title:
            marital_map = {
                'single': 'single',
                'married': 'married',
                'divorced': 'divorced',
                'widower': 'widower',
                'widowed': 'widower',
                'cohabitant': 'cohabitant',
            }
            key = str(answer_value).strip().lower()
            for match, selection_value in marital_map.items():
                if match in key:
                    return {'marital': selection_value}
            return {}

        if 'employee type' in title:
            etype_map = {
                'employee': 'employee',
                'worker': 'worker',
                'student': 'student',
                'trainee': 'trainee',
                'intern': 'trainee',
                'contractor': 'contractor',
                'freelancer': 'freelance',
                'freelance': 'freelance',
            }
            key = str(answer_value).strip().lower()
            for match, selection_value in etype_map.items():
                if match in key:
                    return {'employee_type': selection_value}
            return {}

        # Many2one fields resolved by name lookup
        if 'nationality' in title:
            country = self.env['res.country'].search([('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'country_id': country.id} if country else {}

        if 'department' in title:
            department = self.env['hr.department'].search([('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'department_id': department.id} if department else {}

        if 'work location' in title:
            location = self.env['hr.work.location'].search([('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'work_location_id': location.id} if location else {}

        if title == 'manager':
            manager = self.env['hr.employee'].search(
                [('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'parent_id': manager.id} if manager else {}

        # Bank account: find or create a res.partner.bank and link it
        if 'bank account' in title:
            acc_number = str(answer_value).replace(' ', '').strip()
            if not acc_number:
                return {}
            bank = self.env['res.partner.bank'].search([('acc_number', 'ilike', acc_number)], limit=1)
            if not bank:
                partner = self.work_contact_id
                if partner:
                    bank = self.env['res.partner.bank'].create({
                        'acc_number': acc_number,
                        'partner_id': partner.id,
                    })
            if bank:
                return {'bank_account_ids': [(6, 0, [bank.id])]}
            return {}

        # Skills: match free text against hr.skill and create hr.employee.skill records
        if 'skills' in title:
            skill_vals = []
            raw_values = answer_value if isinstance(answer_value, list) else [answer_value]
            for raw in raw_values:
                for name in str(raw).replace(';', ',').split(','):
                    name = name.strip()
                    if not name:
                        continue
                    skill = self.env['hr.skill'].search([('name', 'ilike', name)], limit=1)
                    if skill:
                        skill_vals.append((0, 0, {'employee_id': self.id, 'skill_id': skill.id}))
            if skill_vals:
                return {'employee_skill_ids': skill_vals}
            return {}

        _logger.info("No field mapping found for question: '%s'", question.title)
        return {}


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    def _mark_done(self):
        """Hook the public survey submission: auto-populate the employee record."""
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