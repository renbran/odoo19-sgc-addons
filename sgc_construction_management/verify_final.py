# Final verification
import datetime
company = env["res.company"].search([], limit=1)
print(f"Currency: {company.currency_id.name} {company.currency_id.symbol}")

# Dashboard KPIs
projects = env["construction.project"].search([])
total_rev = sum(projects.mapped("total_billed"))
total_cost = sum(projects.mapped("total_expenses"))
wip = sum((p.contract_value or 0) - (p.total_billed or 0) for p in projects if p.state == "active")

invoices = env["account.move"].search([("move_type","=","out_invoice"),("state","=","posted"),("payment_state","!=","paid")])
today = datetime.date.today().isoformat()
overdue = env["account.move"].search([("move_type","=","out_invoice"),("state","=","posted"),("payment_state","!=","paid"),("invoice_date_due","<",today)])

print(f"\n=== DASHBOARD KPIs ===")
print(f"Total Revenue: {total_rev:,.0f} {company.currency_id.symbol}")
print(f"Total Costs: {total_cost:,.0f} {company.currency_id.symbol}")
print(f"Net Profit: {total_rev - total_cost:,.0f} {company.currency_id.symbol}")
print(f"WIP Value: {wip:,.0f} {company.currency_id.symbol}")
print(f"Receivables: {sum(invoices.mapped('amount_residual')):,.0f} {company.currency_id.symbol}")
print(f"Overdue: {sum(overdue.mapped('amount_residual')):,.0f} {company.currency_id.symbol}")
print(f"Active WOs: {env['construction.work.order'].search_count([('state','in',['draft','confirmed','in_progress'])])}")
print(f"Critical Risks: {sum(1 for p in projects if p.rag_status == 'red')}")
