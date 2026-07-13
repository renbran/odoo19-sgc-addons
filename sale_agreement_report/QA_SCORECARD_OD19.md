# Sale Agreement Report - QA Scorecard

Date: 2026-03-11
QA Mode: Static validation + live Odoo 19 install-readiness review via MCP
Scale: 1-10 where 10 is highest

## Final Module Score
Overall score: 8.2 / 10

## Score Breakdown
| Area | Score (1-10) | Notes |
|---|---:|---|
| Python syntax validity | 10.0 | Final py_compile run passed with exit code 0 |
| Odoo 19 dependency readiness | 9.5 | Required modules are installed in target Odoo 19 |
| Odoo XML ID compatibility | 9.0 | Referenced core sale/portal/base XML IDs were verified through MCP |
| Data model consistency | 8.5 | Yearly agreement model, migration logic, and SaaS pricing flow are coherent |
| Portal security design | 8.5 | Ownership checks and portal rule design are sound |
| Upload validation hardening | 8.5 | Extension, size, and binary signature checks implemented |
| Report/legal content quality | 7.5 | SaaS agreement content is much stronger, but still needs legal/business review |
| Automated test coverage | 6.5 | Focused tests added, but not yet broad integration/runtime coverage |
| Runtime installation certainty | 6.5 | Module is now visible in Odoo registry, but full install log was not executed here |

## Evidence Collected
1. Python syntax validation command passed:
   - `python -m py_compile models/sale_order.py models/sale_agreement.py controllers/portal_agreement.py migrations/19.0.1.0.0/post-migrate.py tests/test_sale_agreement.py`
   - Exit code: `0`
2. Live Odoo 19 dependency modules confirmed installed:
   - `base`, `sale`, `sale_management`, `web`, `website`, `portal`
3. Live Odoo 19 XML IDs confirmed present:
   - `sale.view_order_form`
   - `sale.sale_menu_root`
   - `sale.model_sale_order`
   - `portal.portal_my_home`
   - `portal.portal_docs_entry`
   - `portal.portal_breadcrumbs`
   - `portal.portal_layout`
   - `portal.portal_searchbar`
   - `portal.pager`
   - `base.group_multi_company`
   - `base.group_portal`
   - `base.group_user`
4. Stale references review passed:
   - No remaining `support_tier`, `support_tier_amount`, `payment_1_amount`, `payment_2_amount`, or `portal.portal_pager` references found in active source.
5. Live Odoo registry status:
   - Module `sale_agreement_report` exists in `ir.module.module`

## Current QA Verdict
Status: Conditionally ready
Meaning: The module is in strong shape for installation, but the final install/upgrade runtime and portal interaction flow should still be executed and logged before calling it fully production ready.

## Highest Risk Remaining
1. Real install/upgrade execution on the target Odoo 19 database was not run from this workspace session.
2. Report wording and liability clauses should be approved by the business/legal owner before customer-facing use.
3. Portal upload/download behavior still needs live browser validation after install.

## Actionable Recommendations
1. Install or upgrade the module now on the target Odoo 19 environment and capture the first full server log.
2. Run one live portal test with a real portal user:
   - open `/my/agreements`
   - open agreement detail
   - download agreement
   - upload valid PDF
   - verify invalid file is rejected
3. Print both reports from backend after install and verify formatting with real customer data.
4. Add one more integration test set later for portal access and migration execution.

## Scoring Summary
- Recommended release confidence: 8.2 / 10
- Recommended next gate: live install + portal smoke test
