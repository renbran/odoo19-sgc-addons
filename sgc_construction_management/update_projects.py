# Update project financial fields from actual records
projects = env["construction.project"].search([])
print("=== Updating project financial fields ===")

for project in projects:
    # Sum RA bills for this project
    ra_bills = env["construction.ra.billing"].search([("project_id", "=", project.id)])
    project_billed = sum(ra_bills.mapped("total_amount"))

    # Sum expenses for this project
    expenses = env["construction.expense"].search([("project_id", "=", project.id)])
    project_expenses = sum(expenses.mapped("amount"))

    # Sum subcontract amounts
    subcontracts = env["construction.subcontract"].search([("project_id", "=", project.id)])
    subcontract_total = sum(subcontracts.mapped("contract_value"))

    # Get latest site diary
    diaries = env["construction.site.diary"].search(
        [("project_id", "=", project.id)], order="date desc", limit=1
    )

    # Get open NCR count
    open_ncrs = env["construction.quality.check"].search_count([
        ("project_id", "=", project.id),
        ("state", "in", ["draft", "in_progress", "failed"])
    ])

    # Calculate margin
    margin = 0
    if project_billed > 0:
        margin = ((project_billed - project_expenses) / project_billed) * 100

    # Calculate budget consumed
    budget_consumed = 0
    if project.contract_value and project.contract_value > 0:
        budget_consumed = (project_expenses / project.contract_value) * 100

    project.write({
        "total_billed": project_billed,
        "total_expenses": project_expenses,
        "margin_percent": round(margin, 2),
        "budget_consumed": round(budget_consumed, 2),
        "open_ncr_count": open_ncrs,
        "last_site_diary": diaries[0].date if diaries else False,
    })
    print(f"  {project.name}:")
    print(f"    contract={project.contract_value:,.0f}, billed={project_billed:,.0f}, "
          f"expenses={project_expenses:,.0f}, margin={margin:.1f}%, budget_used={budget_consumed:.1f}%")
    print(f"    subcontracts={subcontract_total:,.0f}, NCRs={open_ncrs}, "
          f"last_diary={diaries[0].date if diaries else 'None'}")

env.cr.commit()
print("\nDone! All project fields updated.")
