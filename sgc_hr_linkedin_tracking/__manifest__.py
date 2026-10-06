{
    'name': 'SGC HR LinkedIn Tracking',
    'version': '1.0',
    'category': 'Human Resources',
    'summary': 'Tag job applicants that arrive via the LinkedIn alias',
    'author': 'SGC Tech',
    'depends': [
        'hr_recruitment',
        'base_automation',
    ],
    'data': [
        'data/hr_applicant_category.xml',
        'data/automated_actions.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
