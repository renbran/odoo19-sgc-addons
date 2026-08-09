# -*- coding: utf-8 -*-
from datetime import date, datetime
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Survey fields
    onboarding_survey_id = fields.Many2one(
        'survey.survey',
        string='Onboarding Survey',
        help='Survey template used for this employee\'s onboarding'
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
            if employee.onboarding_survey_id:
                base_url = employee.get_base_url()
                # Use the survey's access token or create a temporary one
                survey = employee.onboarding_survey_id
                if survey.access_token:
                    employee.onboarding_survey_link = f"{base_url}/survey/take/{survey.access_token}"
                else:
                    # Generate a token if none exists (should not happen for published surveys)
                    employee.onboarding_survey_link = False
            else:
                employee.onboarding_survey_link = False

    @api.depends('onboarding_survey_deadline', 'onboarding_last_submitted', 'onboarding_state')
    def _compute_onboarding_state(self):
        """Compute the onboarding status based on deadline and submission"""
        for employee in self:
            if not employee.onboarding_survey_id:
                employee.onboarding_state = 'not_started'
                continue
                
            now = fields.Datetime.now()
            
            # Check if expired
            if employee.onboarding_survey_deadline and \
               employee.onboarding_survey_deadline < fields.Date.context_today(employee):
                employee.onboarding_state = 'expired'
                continue
                
            # Check if completed (has submission)
            if employee.onboarding_last_submitted:
                employee.onboarding_state = 'completed'
                continue
                
            # Check if in progress (survey assigned but not submitted)
            if employee.onboarding_survey_id:
                employee.onboarding_state = 'in_progress'
            else:
                employee.onboarding_state = 'not_started'

    def action_generate_onboarding_survey(self):
        """Generate or regenerate the onboarding survey for this employee"""
        self.ensure_one()
        
        # Get or create a default onboarding survey template
        survey_template = self._get_default_onboarding_survey_template()
        if not survey_template:
            raise ValidationError(_("No onboarding survey template available. Please configure one first."))
        
        # Create a copy of the template for this employee
        survey_copy = survey_template.copy({
            'title': f"{survey_template.title} - {self.name}",
            'access_token': False,  # Will be generated when published
            'users_login_required': False,  # Public access
            'scoring_type': 'none',
        })
        
        # Publish the survey to generate access token
        if survey_copy:
            survey_copy.action_publish()
            
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
        
        template = self.env.ref('sgc_employee_onboarding.email_template_employee_onboarding', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=False)
            self.message_post(
                body=_('Onboarding survey link e-mailed to %(email)s.') % {'email': self.work_email},
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        else:
            # Fallback if template doesn't exist yet
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
        """Get or create the default onboarding survey template"""
        # Look for an existing template marked as default
        template = self.env['survey.survey'].search([
            ('title', '=', 'SGC Employee Onboarding Survey'),
            ('is_template', '=', True)
        ], limit=1)
        
        if not template:
            # Create the default template
            template = self._create_default_onboarding_survey_template()
        
        return template

    def _create_default_onboarding_survey_template(self):
        """Create the default onboarding survey template with standard fields"""
        # This will be implemented in the data file
        # For now, return None to indicate template should come from data XML
        return self.env['survey.survey'].search([
            ('title', '=', 'SGC Employee Onboarding Survey'),
            ('is_template', '=', True)
        ], limit=1)

    def _process_survey_submission(self, survey_user_input):
        """Process a submitted survey and map answers to employee fields
        This method will be called from the controller when a survey is submitted
        """
        self.ensure_one()
        if not survey_user_input or survey_user_input.state != 'done':
            return False
            
        # Update last submission timestamp
        self.onboarding_last_submitted = fields.Datetime.now()
        
        # Process each question and map to employee fields
        for line in survey_user_input.user_input_line_ids:
            question = line.question_id
            answer_value = None
            
            # Extract answer based on question type
            if question.question_type == 'char_box':
                answer_value = line.value_char_box
            elif question.question_type == 'text_box':
                answer_value = line.value_text_box
            elif question.question_type == 'date':
                answer_value = line.value_date
            elif question.question_type == 'datetime':
                answer_value = line.value_datetime
            elif question.question_type == 'multiple_choice':
                answer_value = line.value_suggested_choice and line.value_suggested_choice.id
            elif question.question_type == 'multiple_choice_multiple':
                answer_value = line.value_suggested_choice_ids.ids
            elif question.question_type == 'matrix':
                answer_value = line.value_matrix
            # Add more types as needed
            
            # Map question to employee field based on question title or tags
            if answer_value is not None:
                self._map_question_to_employee_field(question, answer_value)
        
        # Mark as completed
        self.onboarding_state = 'completed'
        
        # Notify HR
        self.message_post(
            body=_('Employee %s has completed their onboarding survey.') % self.name,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        
        return True

    def _map_question_to_employee_field(self, question, answer_value):
        """Map a survey question answer to the appropriate employee field
        This uses the question's title or tags to determine the target field
        """
        # Mapping based on question title (case-insensitive, trimmed)
        question_title = (question.title or '').lower().strip()
        
        # Define mappings: question title pattern -> (field_name, conversion_function)
        field_mappings = {
            'work email': ('work_email', lambda x: str(x) if x else False),
            'personal email': ('email', lambda x: str(x) if x else False),
            'work phone': ('work_phone', lambda x: str(x) if x else False),
            'mobile phone': ('mobile_phone', lambda x: str(x) if x else False),
            'home phone': ('home_phone', lambda x: str(x) if x else False),
            'emergency contact': ('emergency_contact', lambda x: str(x) if x else False),
            'emergency phone': ('emergency_phone', lambda x: str(x) if x else False),
            'date of birth': ('birthday', lambda x: x if isinstance(x, date) else False),
            'marital status': ('marital', lambda x: str(x) if x else False),
            'number of children': ('children', lambda x: int(x) if x else False),
            'nationality': ('country_id', lambda x: x if isinstance(x, int) else False),
            'department': ('department_id', lambda x: x if isinstance(x, int) else False),
            'job position': ('job_title', lambda x: str(x) if x else False),
            'work location': ('work_location_id', lambda x: x if isinstance(x, int) else False),
            'manager': ('parent_id', lambda x: x if isinstance(x, int) else False),
            'employee type': ('employee_type', lambda x: str(x) if x else False),
            'bank account': ('bank_account_id', lambda x: x if isinstance(x, int) else False),
            'passport number': ('passport_id', lambda x: str(x) if x else False),
            'visa number': ('visa_number', lambda x: str(x) if x else False),
            'visa expiration': ('visa_expire', lambda x: x if isinstance(x, date) else False),
            'visa type': ('visa_type', lambda x: str(x) if x else False),
            'skills': ('skill_ids', lambda x: [(6, 0, x)] if isinstance(x, list) else False),
        }
        
        # Check for exact match first
        for pattern, (field_name, converter) in field_mappings.items():
            if pattern in question_title:
                try:
                    converted_value = converter(answer_value)
                    if converted_value is not False:  # Only set if not explicitly False
                        self.write({field_name: converted_value})
                    return
                except Exception as e:
                    _logger.warning(f"Failed to map question '{question.title}' to field '{field_name}': {e}")
                    return
        
        # If no mapping found, log for debugging
        _logger.info(f"No field mapping found for question: '{question.title}'")

