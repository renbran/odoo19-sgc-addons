"""Onboarding survey fields and actions on hr.employee."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    # Identity fields not provided by Odoo 19 core (passport/visa expiry live on hr.version)
    visa_number = fields.Char(string="Visa Number", groups="hr.group_hr_user", tracking=True)
    visa_type = fields.Char(string="Visa Type", groups="hr.group_hr_user", tracking=True)

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
        for employee in self:
            survey = employee.onboarding_survey_id
            if survey and survey.access_token:
                employee.onboarding_survey_link = "%s/survey/start/%s" % (
                    employee.get_base_url(), survey.access_token)
            else:
                employee.onboarding_survey_link = False

    @api.depends('onboarding_survey_deadline', 'onboarding_last_submitted', 'onboarding_state')
    def _compute_onboarding_state(self):
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
        return self.env['survey.survey'].search([
            ('title', '=', 'SGC Employee Onboarding Survey'),
        ], limit=1)