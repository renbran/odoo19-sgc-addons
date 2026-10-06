# Test that the new hook functions are importable
import sys
if "odoo.addons.sgc_construction_management.hooks" in sys.modules:
    del sys.modules["odoo.addons.sgc_construction_management.hooks"]

from odoo.addons.sgc_construction_management.hooks import (
    _set_company_currency_aed,
    _ensure_chart_of_accounts,
    _ensure_journals,
    _populate_project_financials,
    _seed_overdue_invoices,
)
print("All new functions imported successfully")

# Verify current state
company = env["res.company"].search([], limit=1)
print(f"Company currency: {company.currency_id.name} {company.currency_id.symbol}")
print(f"Accounts: {env['account.account'].search_count([])}")
print(f"Journals: {env['account.journal'].search_count([])}")

# Test that _set_company_currency_aed doesn't crash
print("\nTesting _set_company_currency_aed...")
_set_company_currency_aed(env)
company = env["res.company"].search([], limit=1)
print(f"Currency after call: {company.currency_id.name}")

# Test that _ensure_chart_of_accounts is idempotent
print("\nTesting _ensure_chart_of_accounts (should be no-op, already have accounts)...")
_ensure_chart_of_accounts(env)
print(f"Accounts still: {env['account.account'].search_count([])}")

# Test that _ensure_journals is idempotent
print("\nTesting _ensure_journals (should be no-op, already have journals)...")
_ensure_journals(env)
print(f"Journals still: {env['account.journal'].search_count([])}")

# Test project financials rollup
print("\nTesting _populate_project_financials...")
_populate_project_financials(env)
for p in env["construction.project"].search([]):
    print(f"  {p.name[:40]}: billed={p.total_billed:,.0f}, expenses={p.total_expenses:,.0f}")

# Test overdue seeding
print("\nTesting _seed_overdue_invoices...")
_seed_overdue_invoices(env)
invoices = env["account.move"].search([("move_type", "=", "out_invoice")], order="name")
for inv in invoices:
    print(f"  {inv.name}: due {inv.invoice_date_due}")

print("\nAll hook functions work correctly!")
