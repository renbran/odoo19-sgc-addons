from odoo import fields
from odoo.tests.common import TransactionCase


class TestOnboardingSubmission(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.env['survey.survey'].search(
            [('title', '=', 'SGC Employee Onboarding Survey')], limit=1)
        cls.employee = cls.env['hr.employee'].create({
            'name': 'E2E Regression Employee',
            'work_email': 'e2e.regression@scholarixglobal.com',
        })
        cls.employee.action_generate_onboarding_survey()
        cls.survey = cls.employee.onboarding_survey_id

    def _question(self, title):
        return self.env['survey.question'].search(
            [('survey_id', '=', self.survey.id), ('title', '=', title)], limit=1)

    def _add_answer(self, user_input, question, answer_type, **vals):
        return self.env['survey.user_input.line'].create({
            'user_input_id': user_input.id,
            'question_id': question.id,
            'answer_type': answer_type,
            **vals,
        })

    def _submit(self, answers):
        user_input = self.env['survey.user_input'].create({
            'survey_id': self.survey.id,
            'state': 'in_progress',
        })
        for title, answer_type, vals in answers:
            self._add_answer(user_input, self._question(title), answer_type, **vals)
        user_input._mark_done()
        return user_input

    def test_template_loaded_with_all_questions(self):
        self.assertTrue(self.template)
        questions = self.template.question_ids.filtered(lambda q: not q.is_page)
        self.assertEqual(len(questions), 22)

    def test_generate_survey_makes_public_copy(self):
        self.assertTrue(self.survey)
        self.assertTrue(self.survey.access_token)
        self.assertIn('survey/start/', self.employee.onboarding_survey_link)
        self.assertEqual(self.employee.onboarding_state, 'in_progress')

    def test_submission_maps_answers_to_employee_fields(self):
        self._submit([
            ('Work Email', 'char_box', {'value_char_box': 'e2e.work@scholarixglobal.com'}),
            ('Personal Email', 'char_box', {'value_char_box': 'e2e.personal@gmail.com'}),
            ('Mobile Phone', 'char_box', {'value_char_box': '+971501234567'}),
            ('Emergency Contact', 'char_box', {'value_char_box': 'Jane Doe'}),
            ('Date of Birth', 'date', {'value_date': '1990-05-15'}),
            ('Marital Status', 'suggestion', {
                'suggested_answer_id': self._suggested_answer('Married').id,
            }),
            ('Number of Dependent Children', 'numerical_box', {'value_numerical_box': 2}),
            ('Nationality', 'char_box', {'value_char_box': 'United Arab Emirates'}),
            ('Job Position', 'char_box', {'value_char_box': 'Senior Developer'}),
            ('Department', 'char_box', {'value_char_box': 'IT'}),
            ('Visa Number', 'char_box', {'value_char_box': 'V1234567'}),
            ('Visa Expiration Date', 'date', {'value_date': '2027-01-01'}),
            ('Skills', 'text_box', {'value_text_box': 'Python, SQL, Odoo'}),
        ])
        self.assertEqual(self.employee.work_email, 'e2e.work@scholarixglobal.com')
        self.assertEqual(self.employee.private_email, 'e2e.personal@gmail.com')
        self.assertEqual(self.employee.mobile_phone, '+971501234567')
        self.assertEqual(self.employee.birthday, fields.Date.to_date('1990-05-15'))
        self.assertEqual(self.employee.marital, 'married')
        self.assertEqual(self.employee.children, 2)
        self.assertEqual(self.employee.country_id.name, 'United Arab Emirates')
        self.assertEqual(self.employee.job_title, 'Senior Developer')
        self.assertTrue(self.employee.department_id)
        self.assertEqual(self.employee.department_id.name, 'IT')
        self.assertEqual(self.employee.visa_number, 'V1234567')
        self.assertEqual(self.employee.visa_expire, fields.Date.to_date('2027-01-01'))
        self.assertEqual(self.employee.onboarding_state, 'completed')
        self.assertTrue(self.employee.onboarding_last_submitted)
        self.assertEqual(len(self.employee.employee_skill_ids), 3)

    def test_unmapped_question_is_ignored(self):
        self._submit([
            ('Work Email', 'char_box', {'value_char_box': 'e2e.work@scholarixglobal.com'}),
            ('Favorite Color', 'char_box', {'value_char_box': 'Blue'}),
        ])
        self.assertEqual(self.employee.onboarding_state, 'completed')
        self.assertEqual(self.employee.work_email, 'e2e.work@scholarixglobal.com')

    def test_idempotent_submission(self):
        user_input = self._submit([
            ('Work Email', 'char_box', {'value_char_box': 'e2e.work@scholarixglobal.com'}),
        ])
        employee = self.employee
        before = employee.onboarding_last_submitted
        result = self.employee._process_survey_submission(user_input)
        self.assertTrue(result)
        self.assertEqual(employee.onboarding_last_submitted, before)

    def _suggested_answer(self, value):
        return self.env['survey.question.answer'].search([
            ('question_id', '=', self._question('Marital Status').id),
            ('value', '=', value),
        ], limit=1)