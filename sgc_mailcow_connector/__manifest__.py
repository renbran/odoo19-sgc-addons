{
    "name": "SGC - Mailcow Connector",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Manage Mailcow mailboxes from Odoo: create, disable, sync, "
               "and auto-provision SMTP/IMAP servers for employees.",
    "description": """
Mailcow Connector
=================
- Configure the Mailcow API connection in Settings (URL, API key, defaults).
- Create employee mailboxes in Mailcow directly from Odoo.
- Disable / re-enable mailboxes without deleting them (mail is preserved).
- Auto-provision the matching outgoing SMTP server and incoming IMAP
  (fetchmail) server in Odoo, following the per-user pattern.
- Polling sync cron keeps Odoo in step with Mailcow (Mailcow has no
  native webhooks).
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    # fetchmail.server is part of "mail" in Odoo 19 (no standalone module)
    "depends": ["base_setup", "mail", "hr", "website_slides"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "data/res_users_actions.xml",
        "data/email_templates.xml",
        "data/report_actions.xml",
        "reports/warning_letter_template.xml",
        "reports/nda_template.xml",
        "reports/company_asset_handover_template.xml",
        "views/mailcow_mailbox_views.xml",
        "views/res_config_settings_views.xml",
        "views/hr_employee_views.xml",
    ],
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "application": False,
}
