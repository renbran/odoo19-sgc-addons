{
    "name": "SGC Accounting Agents",
    "version": "19.0.1.4.0",
    "category": "Accounting/Accounting",
    "summary": "Least-privilege access control for the accounting agent workforce",
    "description": """
Access control for the accounting agents.
===============================

Every accounting agent gets its own service user, its own API key and exactly
one role group.  A role group grants only the models and operations that the
role job description allows, so an agent cannot perform work that belongs to
another role.

Roles
-----
* ``agent-00-gatekeeper``: reads documents, validates them, requests approvals.
* ``agent-01-intake``: creates draft invoices and bills from extracted documents.
* ``agent-02-posting``: maps GL accounts and posts approved drafts only.
* ``agent-03-reconciliation``: reconciles bank statement lines.
* ``agent-04-tax-audit``: audits VAT and corporate tax, read-only on the ledger.
* ``agent-05-reporting``: builds management reports, read-only on the ledger.
* ``agency-manager``: approves postings and manages the agent credentials.

Guards
------
* Agents cannot post a journal entry without an approved
  ``sgc.agent.posting.approval`` record.
* Agents cannot create, cancel, reset or delete journal entries outside their
  role.
* Every agent action is written to ``sgc.agent.audit``.

Tax Audit
---------
* ``sgc.agent.tax.audit`` validates the VAT output/input grid for a period,
  detects missing output VAT, unexpected rates, and records findings as
  ``sgc.agent.report`` entries with a full audit trail. A monthly cron runs
  a VAT audit for the previous quarter for every company.
""",
    "author": "SGC TECH AI",
    "license": "LGPL-3",
    "depends": ["base", "account", "mail"],
    "data": [
        "security/sgc_accounting_agents_groups.xml",
        "security/ir.model.access.csv",
        "security/ir.rule.xml",
        "data/sgc_agent_role_data.xml",
        "data/sgc_agent_tax_audit_cron.xml",
    ],
    "installable": True,
    "application": False,
}
