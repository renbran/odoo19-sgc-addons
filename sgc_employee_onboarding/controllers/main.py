# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class EmployeeOnboardingController(http.Controller):

    @http.route('/employee/onboarding/sumbit/<string:survey_token>', type='json', auth='public', website=True, csrf=False)
    def submit_onboarding_survey(self, survey_token, **post):
        """Handle survey submission from public link and map to employee fields"""
        try:
            # Find the survey user input by token
            survey_user_input = request.env['survey.user_input'].sudo().search([
                ('survey_id.access_token', '=', survey_token),
                ('state', '=', 'done')
            ], limit=1, order='create_date desc')
            
            if not survey_user_input:
                _logger.warning(f"Invalid or expired survey token: {survey_token}")
                return {'error': _('Invalid or expired survey link.')}
            
            # Find the employee associated with this survey
            # We need to trace back: survey_user_input -> survey -> ??? -> employee
            # Since we don't have a direct link, we'll use the survey title or other metadata
            survey = survey_user_input.survey_id
            
            # Look for employee whose onboarding_survey_id matches this survey
            # or whose name appears in the survey title
            employee = request.env['hr.employee'].sudo().search([
                '|',
                ('onboarding_survey_id', '=', survey.id),
                ('name', 'ilike', survey.title.split(' - ')[0] if ' - ' in survey.title else survey.title)
            ], limit=1)
            
            if not employee:
                _logger.warning(f"No employee found for survey: {survey.title} (ID: {survey.id})")
                return {'error': _('Could not associate survey with an employee.')}
            
            # Process the submission and map to employee fields
            success = employee._process_survey_submission(survey_user_input)
            
            if success:
                return {
                    'status': 'success',
                    'message': _('Thank you for completing your onboarding survey!'),
                    'redirect_url': '/web'
                }
            else:
                return {'error': _('Failed to process survey submission.')}
                
        except Exception as e:
            _logger.exception(f"Error processing onboarding survey submission: {e}")
            return {'error': _('An error occurred while processing your submission.')}

