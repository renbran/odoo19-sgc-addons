{
    "name": "SGC Report Theme - Customer Email Templates",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Re-styles the customer-facing quotation/proforma/invoice/receipt "
               "emails onto the SGC TECH AI brand, matching the existing "
               "meeting-invitation email design.",
    "description": """
SGC Report Theme - Customer Email Templates
==============================================

Re-points 4 stock mail.template records (re-declared here by their exact
fully-qualified XML ID, a standard Odoo customization pattern - Odoo
updates the existing record rather than creating a duplicate) onto the
SGC TECH AI brand email design:

- sale.email_template_edi_sale (Sales: Send Quotation)
- sale.email_template_proforma (Sales: Send Proforma)
- account.email_template_edi_invoice (Invoice: Sending)
- account.mail_template_data_payment_receipt (Payment: Payment Receipt)

Every t-if/t-out business-logic expression from each stock template's
original body_html is preserved exactly (doc_name branching, origin
reference, product documents list, payment_state/payment_reference/bank
account branching, timesheet portal link, signature blocks) - only the
presentation changes, via sgc_report_theme_core.email_shell_sgc (the
reusable chrome extracted from sgc_meeting_ai's already-live "Active
Meeting Invitation (SGC)" template, which is this brand's approved email
design reference). email_layout_xmlid is set to False on each, matching
that reference template - these are fully self-contained branded emails,
not wrapped through the stock mail.mail_notification_layout.

Uninstalling this module reverts all 4 templates to their stock body/layout.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "sale", "account"],
    "data": [
        "data/email_templates_sgc.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
