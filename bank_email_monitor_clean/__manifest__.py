{
    "name": "Bank Email Monitor",
    "version": "19.0.2.0.0",
    "summary": "Rule-based bank email parsing with learning and reconciliation hints",
    "description": "Monitors bank notification emails, stages transactions, suggests reconciliation, and learns draft vendor rules.",
    "author": "OdooFinanceArchitect",
    "category": "Accounting/Banking",
    "depends": ["account", "mail", "base_setup"],
    "data": [
        "security/ir.model.access.csv",
        "security/bank_email_transaction_rules.xml",
        "views/bank_email_transaction_views.xml",
        "views/bank_vendor_rule_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml"
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
