{
    "name": "SGC Payment-Based Bank & Cash Reconciliation",
    "version": "19.0.1.0.1",
    "category": "Accounting",
    "summary": "Turns registered payments into bank/cash statement lines and reconciles them, "
               "so bank and cash journals reconcile without importing a bank statement.",
    "author": "SGC TECH AI",
    "license": "OPL-1",
    "depends": ["account"],
    "data": [
        "data/ir_cron.xml",
        "views/account_journal_views.xml",
    ],
    "installable": True,
}
