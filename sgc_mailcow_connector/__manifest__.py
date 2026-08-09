{
    "name": "SGC - Mailcow Connector",
    "version": "19.0.1.2.0",
    "category": "Discuss",
    "summary": "Manage Mailcow mailboxes from Odoo: create, disable, sync, "
                 "and auto-provision SMTP/IMAP servers for employees.",
    "description": """
    "Mailcow Connector\n================\n- Configure the Mailcow API connection in Settings (URL, API key, defaults).\n- Create employee mailboxes in Mailcow directly from Odoo.\n- Disable / re-enable mailboxes without deleting them (mail is preserved).\n- Auto-provision the matching outgoing SMTP server and incoming IMAP\n  (fetchmail) server in Odoo, following the per-user pattern.\n- Polling sync cron keeps Odoo in step with Mailcow (Mailcow has no\n  native webhooks).\n""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    # fetchmail.server is part of "mail" in Odoo 19 (no standalone module)
    "depends": ["base_setup", "mail", "hr", "portal", "website_slides"],
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "data/ir_cron.xml",
        "data/sequences.xml",
        "data/res_users_actions.xml",
        # Email templates AFTER report_actions to reference report_template_ids
        "data/report_actions.xml",
        "data/email_templates.xml",
        "reports/warning_letter_template.xml",
        "reports/nda_template.xml",
        "reports/company_asset_handover_template.xml",
        "views/sgc_employee_document_views.xml",
        "views/mailcow_mailbox_views.xml",
        "views/res_config_settings_views.xml",
        "views/hr_employee_views.xml",
        "views/portal_templates.xml",  # NEW
    ],
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "application": False,
}