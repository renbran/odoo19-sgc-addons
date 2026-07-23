{
    "name": "SGC Construction - Statement of Account Balance Fix",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Fixes the Statement of Account report's balance to reflect "
                "actual outstanding amounts, and adds total/summary rows.",
    "description": """
SGC Construction - Statement of Account Balance Fix
=======================================================

2026-07-23: user-reported bug - sgc_construction_management's
"Statement of Account" report (report_soa_template) shows an incorrect
balance. Root cause confirmed against live data (partner id 8, OSUS REAL
ESTATE BROKERAGE LLC): the template sums amount_total for every posted
invoice regardless of payment_state, so the running "Balance" column is
really the cumulative TOTAL EVER INVOICED, not what is actually still
owed. Of that partner's 32 posted invoices, 28 (AED 97,421.13) are
already fully paid, yet still counted toward "Balance", inflating it to
~AED 115,477.71 when the true outstanding amount is AED 18,056.58
(confirmed to match sgc_report_theme_statement's independently-computed
figure for the same partner).

Fix (via inherit_id XPath on report_soa_template, not editing
sgc_construction_management's file directly):
- The "Amount" column is UNCHANGED - it still shows each transaction's
  full invoiced/credited amount (a correct historical record).
- The "Balance" column now accumulates amount_residual (the actual
  outstanding portion of each invoice) instead of amount_total - a paid
  invoice contributes 0 to the balance, exactly as it should.
- Adds a highlighted totals row (Total Invoiced / Outstanding Balance)
  and a mini summary above the table, using this module's own existing
  Bootstrap-based visual language (table-info, bg-light) rather than
  introducing a dependency on the separate sgc_report_theme_core system,
  since sgc_construction_management intentionally keeps its own theme.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_construction_management"],
    "data": [
        "views/soa_balance_fix.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
