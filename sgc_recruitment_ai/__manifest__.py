{
    "name": "SGC - Recruitment AI",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Recruitment",
    "summary": "AI-assisted recruitment enhancements",
    "author": "SmartClinic",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["base", "hr_recruitment", "mail"],
    "data": [
        "data/fetchmail_data.xml",
        "data/mail_layout_overrides.xml",
        "views/hr_applicant_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
