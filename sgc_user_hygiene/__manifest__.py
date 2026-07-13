{
    "name": "SGC User Hygiene",
    "version": "19.0.1.0.0",
    "summary": "Normalize user logins and partner emails to lowercase to prevent login-mismatch issues.",
    "description": "Forces res.users.login and res.partner.email to be stored in lowercase so that the case-sensitivity of the Odoo login field cannot break user authentication (e.g. Rajeshwari@sgctech.ai vs rajeshwari@sgctech.ai).",
    "author": "SGC Tech",
    "license": "LGPL-3",
    "category": "Tools",
    "depends": [
        "base",
        "auth_signup"
    ],
    "data": [
        "views/res_config_settings_view.xml"
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
