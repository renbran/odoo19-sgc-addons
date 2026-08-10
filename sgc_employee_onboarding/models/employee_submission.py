"""Survey submission processing: map answers onto the employee record."""
from datetime import date

from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _process_survey_submission(self, survey_user_input):
        self.ensure_one()
        if not survey_user_input or survey_user_input.state != 'done' or survey_user_input.test_entry:
            return False
        # Idempotency guard: never process the same submission twice
        if self.onboarding_last_user_input_id.id == survey_user_input.id:
            return True

        lines = survey_user_input.user_input_line_ids.filtered(lambda line: not line.skipped)
        answers_by_question = {}
        for line in lines:
            question_id = line.question_id.id
            answers_by_question.setdefault(question_id, self.env['survey.user_input.line'])
            answers_by_question[question_id] |= line

        vals = {}
        for question_id, question_lines in answers_by_question.items():
            question = self.env['survey.question'].browse(question_id)
            answer_value = self._extract_answer_value(question, question_lines)
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

    @api.model
    def _get_default_skill_level(self, skill_type):
        level = self.env['hr.skill.level'].search(
            [('skill_type_id', '=', skill_type.id)], order='id', limit=1)
        if not level:
            level = self.env['hr.skill.level'].create({
                'name': 'Level 1',
                'skill_type_id': skill_type.id,
            })
        return level

    def _map_question_to_employee_field(self, question, answer_value):
        """Return the {field: value} dict to write on the employee, or {} if unmapped."""
        title = (question.title or '').strip().lower()
        if not title or answer_value is None:
            return {}

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

        if 'date of birth' in title:
            return {'birthday': answer_value} if isinstance(answer_value, date) else {}
        if 'visa expiration' in title:
            return {'visa_expire': answer_value} if isinstance(answer_value, date) else {}

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
            dept_name = str(answer_value).strip()
            department = self.env['hr.department'].search([('name', '=ilike', dept_name)], limit=1)
            if not department:
                department = self.env['hr.department'].create({'name': dept_name})
            return {'department_id': department.id}

        if 'work location' in title:
            location = self.env['hr.work.location'].search([('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'work_location_id': location.id} if location else {}

        if title == 'manager':
            manager = self.env['hr.employee'].search(
                [('name', 'ilike', str(answer_value).strip())], limit=1)
            return {'parent_id': manager.id} if manager else {}

        # Bank account: find-or-create a linked res.partner.bank
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

        # Skills: find-or-create hr.skill and hr.employee.skill records
        if 'skills' in title:
            skill_vals = []
            raw_values = answer_value if isinstance(answer_value, list) else [answer_value]
            for raw in raw_values:
                for name in str(raw).replace(';', ',').split(','):
                    name = name.strip()
                    if not name:
                        continue
                    skill = self.env['hr.skill'].search([('name', '=ilike', name)], limit=1)
                    if not skill:
                        skill_type = self.env['hr.skill.type'].search([], order='id', limit=1)
                        if not skill_type:
                            skill_type = self.env['hr.skill.type'].create({'name': 'General'})
                        skill = self.env['hr.skill'].create({
                            'name': name, 'skill_type_id': skill_type.id,
                        })
                    skill_vals.append((0, 0, {
                        'skill_id': skill.id,
                        'skill_type_id': skill.skill_type_id.id,
                        'skill_level_id': self._get_default_skill_level(skill.skill_type_id).id,
                    }))
            if skill_vals:
                return {'employee_skill_ids': skill_vals}
            return {}

        _logger.info("No field mapping found for question: '%s'", question.title)
        return {}