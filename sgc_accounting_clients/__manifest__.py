# -*- coding: utf-8 -*-
{
    "name": "SGC Accounting Clients",
    "version": "19.0.1.2.0",
    "category": "Accounting/Accounting",
    "summary": "Multi-company accounting client registry, document intake and portal",
    "description": """
SGC Accounting Clients
======================

Registry and client portal for the SGC accounting agency on app.sgctech.ai.

* One accounting workspace per client, with one or more companies per workspace.
* Client portal at /my/accounting: workspace list, company list, nine document
  intake buckets with downloadable CSV format guides, upload history and
  download.
* Deterministic intake metadata: SHA-256, document type, target company, uploader,
  storage path and validation state.
* Provisioning outbox for the future accounting tenant receiver. This module does
  not provision or modify tenant databases by itself.
* Writes accounting routing context onto res.partner so agents can resolve the
  client database, workspace URL, storage root and company list.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["base", "mail", "portal", "account"],
    "data": [
        "security/accounting_security.xml",
        "security/ir.model.access.csv",
        "data/accounting_data.xml",
        "views/accounting_client_views.xml",
        "views/accounting_company_views.xml",
        "views/accounting_upload_views.xml",
        "views/accounting_agent_views.xml",
        "views/accounting_provision_views.xml",
        "views/res_partner_views.xml",
        "views/portal_templates.xml",
        "views/menus.xml",
        "data/accounting_agent_cron.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

