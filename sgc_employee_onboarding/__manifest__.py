{
    'name': 'SGC Employee Onboarding Surveys',
    'version': '19.0.1.3.0',
    'category': 'Human Resources',
    'summary': 'Employee onboarding with survey forms mapped to employee fields',
    'description': """
Employee onboarding using Odoo Survey module to collect structured data
that is automatically mapped and stored in hr.employee fields.

Features:
- Public survey links for employees to complete onboarding forms
- Automatic mapping of survey answers to employee fields
- Configurable survey templates per employee type/role
- Progress tracking and completion status
- Email notifications for HR when onboarding is complete
""",
    'author': 'Scholarix Global Consultants',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'hr',
        'hr_skills',
        'survey',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/employee_onboarding_survey_template.xml',
        'data/email_templates.xml',
        'static/src/xml/survey_file_upload.xml',
        'views/hr_employee_views.xml',
    ],
    'assets': {
        'survey.survey_assets': [
            'sgc_employee_onboarding/static/src/interactions/survey_file_upload.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
