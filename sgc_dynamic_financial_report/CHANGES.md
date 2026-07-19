# SGC Dynamic Financial Reports - Changelog

## Version 19.0.1.0.0 (2026-07-19) - Rebranding pass (SGC-BRAND.md compliance)

Brought the module into compliance with the `branding/SGC-BRAND.md` contract,
which had previously been left as a known follow-up. `SGC-BRAND.md` itself
was also corrected in this pass: the canonical author/maintainer string is
now the full **"SGC TECH AI"**, not the short "SGC TECH" form used in the
original contract text.

### Manifest (`__manifest__.py`)
- `name`: `"SGC Dynamic Financial Reports"` -> `"Dynamic Financial Reports"`
  (Odoo Store rule: public display name must be <=25 chars and must not
  contain the company name - brand now shows via author/website/icon
  instead).
- `author`/added `company`/`maintainer`: `"SGC TECH AI"` (author was already
  correct; company/maintainer were missing entirely).
- `website`: `https://sgctechai.com` -> `https://sgctech.ai` (canonical
  domain per SGC-BRAND.md).
- added `support`: `info@sgctech.ai`.
- `license`: `LGPL-3` -> `OPL-1` (proprietary marketplace license per brand
  contract - this is a real licensing-terms change, not cosmetic).
- Removed a stale "OWL 2.0 interactive frontend widget" description bullet -
  those JS files were deleted earlier in the audit (dead code referencing
  removed Odoo APIs) and the claim was no longer true.

### Copyright headers
- All 23 `.py` files and 5 `.xml` data/view files: old header block
  (`Part of SGC TECH AI` / `Copyright (c) 2025 ... (sgctechai.com)` /
  `License LGPL-3.0 ...`) replaced with the corrected
  `Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)` header, license
  reference dropped from every file header (OPL-1 terms live in the
  manifest + a LICENSE file, not repeated per-file).
- `README.md`: license and author/website lines corrected to match; removed
  the same stale OWL widget claim.

### Marketplace assets
- Added `sgc_dynamic_financial_report` to `brand_asset/generate_brand.py`'s
  `MODULES` registry and generated `static/description/banner.png` (1500x500)
  + `icon.png` (256x256) from the canonical brand master
  (`brand_asset/banner.png` + `brand_asset/favicon_io/`), matching the
  banner template used across the rest of the SGC module line. Note: the
  generator's `REPO` path assumes modules sit directly under the repo root;
  this repo nests them under `addons/`, so the output path was corrected
  for this run (module-generator-wide fix left as a follow-up, not applied
  here to avoid touching the other 18 modules' outputs unrequested).
- Added `static/description/index.html` - Odoo Store listing page in the
  same navy/gold/cream template used by sibling modules, built from four of
  the real report screenshots captured during the earlier live UI-testing
  pass (not mockups). Verified by rendering it in a browser before
  finishing (hero, feature grid, and screenshot sections all confirmed to
  render correctly, real Partner Ledger screenshot loads).

## Version 19.0.1.0.0 (2026-07-19) - Verified against a real Odoo 19 install

Installed and tested against a genuine local Odoo 19.0-20251222 instance
(Docker, disposable database) - not just static review. That live pass found
**13 more real bugs** the static-only audit below had missed (mostly Odoo 19
storage/schema changes no amount of reading the code would surface without
actually booting a registry against it), fixed one by one until:

```
0 failed, 0 error(s) of 8 tests when loading database 'sgc_dfr_test_20260719'
```

with a clean `-i sgc_dynamic_financial_report` install (607 queries, 18
account-type mappings seeded) on top of it.

### Fixed (found via live install/test, not static review)
- `post_init_hook` manifest value must be a bare name resolvable via
  `getattr(module, name)` - dotted paths (`"hooks.post_init_hook.foo"`) are
  **not** resolved by Odoo's loader; re-exported the function from the
  package's `__init__.py` instead.
- Search-view `<group expand="0" string="Group By">` is no longer valid
  Odoo 19 markup for group-by filters - `expand`/`string` attributes were
  dropped; core modules now use a bare `<group>`.
- A `<menuitem>` can declare `web_icon` only when it has **no** `parent`
  (true root/app menu); ours is nested under Accounting's menu, so
  `web_icon` had to be dropped from it (RNG-schema-enforced, not optional).
- `ir.ui.menu.groups_id` was renamed to `group_ids`.
- `account.account.company_id` was replaced by a `company_ids` Many2many
  (17+ shared chart of accounts) - fixed the wizard's account domain and two
  raw-SQL joins (now via `account_account_res_company_rel`).
- `account.account.code` is a compute over `code_store`, a
  `company_dependent` field stored as JSONB keyed by company id; and
  `account.account.name` / `account.tax.name` / `account.tax.description`
  are `translate=True`, stored as JSONB keyed by lang code (Odoo 17+ moved
  ALL translated field storage to JSONB) - raw SQL selecting these as plain
  columns failed outright; fixed with `->>` JSON extraction.
- The aged-receivable/payable SQL's tax-report cousin
  (`account_move_line_account_tax_rel`) does not have an
  `account_tax_line_id` column - the correct relation is
  `(account_move_line_id, account_tax_id)`, i.e. base-line -> its taxes, not
  tax-line -> base-line. Rewrote as two CTEs (`tax_lines`, `base_lines`)
  instead of one joined-and-grouped query, which also fixed a fan-out bug:
  a tax line linked to several base lines (or vice versa) was being
  `SUM()`-multiplied under the old single-join shape.
- `sgc.financial.report.engine` is an `AbstractModel` (no DB table) but was
  called via `.create({})` in 11 places (wizard, controller, all 9 XLSX
  reports) - `.create()` on an abstract model always fails; removed
  `ensure_one()` from `_generate_report` and called the bare
  `env['sgc.financial.report.engine']` recordset directly everywhere.
- **Financial-correctness bug** (not an Odoo-19 change, pre-existing):
  every report computed `balance` as `debit - credit` uniformly, which is
  the natural sign for asset/expense accounts but inverted for
  liabilities/equity/revenue (normal credit balance) - Balance Sheet showed
  Assets and "Liabilities + Equity" with opposite signs instead of equal
  magnitudes, P&L's net income was computed backwards, and Aged Payable
  showed amounts owed as negative numbers. Added a `natural_balance` /
  `comp_natural_balance` field (sign-flipped for liabilities/equity/revenue)
  used by Balance Sheet and P&L; Aged Payable's bucket SQL now negates
  `aml.balance` for the payable case. Trial Balance intentionally keeps the
  raw debit-credit convention (that's correct there). **Not yet audited**:
  Cash Flow likely has the same sign issue in its activity classification -
  left alone this pass since it's an already-approximate indirect-method
  calculation and no test currently exercises its sign correctness; flagging
  for a follow-up rather than risking a hasty fix to unvalidated logic.
- `sgc.dfr.account.type`'s old-style `_sql_constraints` list is silently
  **not enforced** in Odoo 19 (registry logs a warning, creates no
  constraint) - converted to the new `models.Constraint` class-attribute API.
- `period_from`/`period_to` (`Many2one("account.period")`) and
  `fiscal_year_id` (`Many2one("account.fiscal.year")`) pointed at models
  that don't exist in modern Odoo (`account.period` was removed long before
  v17) and were never actually read by the report engine either - removed
  the fields and the two dead `date_filter` options ("Fiscal Period"/
  "Fiscal Year") that exposed them; only "Date Range" was ever wired up.
- `res.groups` no longer has `category_id` (grouping moved to a
  `res.groups.privilege` record referenced via `privilege_id`) or a plain
  `users` field (renamed `user_ids`) - added a `res.groups.privilege`
  record and updated both.
- Manifest `data` list loaded `data/sgc_report_actions.xml` (which
  `ref`s a view id) before `views/sgc_wizard_views.xml` (which defines that
  view) - reordered.
- `account.move.line.analytic_tag_ids` / `account.analytic.tag` don't exist
  in modern Odoo (17+ moved to a JSON `analytic_distribution` field, no
  separate "tags" concept) - removed the field/domain clause; kept analytic
  *account* filtering via the now-correct `distribution_analytic_account_ids`
  searchable field.
### Fixed (static review, before the live pass - see full list at bottom)
The initial 2025-07-19 release below was built against a pre-Odoo-17 API and
did not install on Odoo 19. A first, static-only review found and fixed:

### Fixed
- **Install-breaking**: replaced all references to the removed
  `account.account.type` model (a `Many2one` field, the post-init hook, and
  two raw-SQL joins powering every one of the 9 reports) with the
  `account.account.account_type` selection field Odoo 17+ actually uses.
- **Install-breaking**: malformed XML tag in `views/sgc_report_templates.xml`
  that prevented the file from parsing at all.
- **Install-breaking**: `attrs="{...}"` view syntax (removed in Odoo 17+)
  replaced with direct `invisible=`/`required=` expressions in the report
  wizard form.
- Fixed a menu item pointing its `action=` at a view id instead of the
  actual `ir.actions.act_window` id (Account Type Mappings config menu did
  nothing).
- Fixed a UX bug where the "Period Comparison" group - which contains the
  checkbox that enables it - was itself hidden until comparison was already
  enabled, making the feature unreachable from the UI.
- Fixed the Aged Receivable/Payable SQL, which referenced an undefined
  `days` column; it now computes days-overdue via a CTE.
- Fixed `equity_unaffected` (Current Year Earnings) being misclassified as
  `'other'` instead of `'equity'` in both the default account-type mapping
  and the Cash Flow financing-activity classification.
- **Security**: closed an IDOR in `/sgc/dfr/preview/<wizard_id>` that let any
  authenticated user fetch another user's/company's generated financial
  report by guessing a wizard id; added group and company checks, and
  re-enabled CSRF protection on the route.
- **Security**: the aging-bucket report SQL spliced a free-text company
  setting (`sgc_dfr_aging_buckets`) unescaped into a SQL column alias -
  switched to positional aliases so the raw label string can never reach the
  query.
- Removed `static/src/js/sgc_action_manager.js` and
  `sgc_financial_report_widget.js` - both used Odoo APIs removed years
  before v19 (`owl.tags`, a dead action-service import path) and were never
  wired into any view; the wizard already renders its result via the
  built-in `widget="html"`.
- Trimmed unused manifest dependencies (`sale`, `purchase`,
  `base_automation`, `mail` - none were referenced anywhere in the code).
- Added `tests/test_financial_reports.py` (TransactionCase): post-init-hook
  seeding/idempotency, all 9 report types generate HTML, Balance Sheet and
  Trial Balance invariants, aging-bucket totals, all 9 XLSX exports.

### Verified
Installed clean and passed all tests against a real, local, disposable Odoo
19.0-20251222 database (`docker exec ... odoo server -i
sgc_dynamic_financial_report --test-enable`): `0 failed, 0 error(s) of 8
tests`. Packaging tarball regenerated and re-verified identical to source.

### Also added
- `static/description/icon.png` (128x128, user-supplied artwork).

### Known follow-ups (not yet done)
- The supplied icon wasn't derived from `brand_asset/sgc-logo.png` via
  `brand_asset/generate_brand.py` per `branding/SGC-BRAND.md` - it's a
  distinct piece of artwork the user provided directly, not the canonical
  brand-generator output. Fine as a placeholder; flag if strict brand-kit
  compliance is required later.
- Manifest author/website/license (`SGC TECH AI` / sgctechai.com / LGPL-3)
  don't match the canonical branding contract (`SGC TECH` / sgctech.ai /
  OPL-1) - needs a product decision, not a code fix.
- Multi-company account visibility (`account_ids` domain, and the SQL join
  via `account_account_res_company_rel`) matches only the exact selected
  company, not `parent_of` hierarchy for the SQL side - the wizard's ORM
  domain does use `parent_of` (matching core Odoo), but the raw-SQL engine
  doesn't replicate that hierarchy walk. Fine for single-company or flat
  multi-company setups; would need parent_path-aware SQL for a parent/child
  company hierarchy.

## Version 19.0.1.0.0 (2026-07-19) - Live UI verification pass

Installed on a genuinely local (non-VPS) Odoo 19 Docker instance, seeded with
a real posted customer invoice and 29 imported `account.payment` records, and
every one of the 9 reports was opened and generated through the actual
browser UI (not just automated tests) to confirm real-world rendering. This
caught **3 more real bugs** the automated test suite hadn't exercised:

### Fixed
- **Crash**: `_default_date_from()` called `fields.Date(year, month, day)` -
  `fields.Date` is the ORM field-descriptor class (like `fields.Char`), not a
  date constructor; it takes at most 2 args, so opening any report wizard on
  a company with a non-calendar fiscal year threw a `TypeError` immediately.
  Fixed to use Python's `datetime.date(...)`.
- **Financial-correctness**: Cash Flow showed revenue as **-$8,500** and
  "Net Change in Cash" as negative for what was actually a cash-positive
  sale - confirmed live in the browser. By the fundamental accounting
  identity (assets = liabilities + equity at all times), the change in cash
  must equal the negative of the combined change in every non-cash account;
  applied a uniform sign flip to `_build_cash_flow`'s activity totals (this
  resolves the "known follow-up" flagged in the previous entry - every
  category needed the same flip, not a per-section one like BS/P&L).
- **Financial-correctness**: Partner Ledger always showed **$0.00 balance**
  for every partner, in every case - confirmed live (Atlas Trading LLC's
  $8,500 outstanding invoice showed as a $0.00 balance). Root cause: the
  partner-balance queries summed *every* journal line tagged with that
  partner, including the invoice's revenue line - and debits always equal
  credits across a fully-recorded move, so the sum necessarily nets to zero
  for any partner, always. Restricted both
  `_query_partner_balances_sql` and the detail-lines domain in
  `_build_partner_ledger` to receivable/payable control accounts only
  (`asset_receivable`, `liability_payable`), matching how a real partner
  ledger is supposed to work.

### Verified
All 9 reports (Balance Sheet, P&L, Cash Flow, Trial Balance, General Ledger,
Partner Ledger, Aged Receivable, Aged Payable, Tax Report) generated
successfully in the browser against real data, screenshotted, and visually
confirmed correct - including re-confirming the two fixes above after
applying them. Screenshots saved under
`video/public/sgc_dynamic_financial_report/` and used to build a product
demo video.

### Still not done
- Multi-company `parent_of` hierarchy in the raw-SQL engine (see previous
  entry - unrelated to this pass, still open).
- `static/description/icon.png` branding-kit provenance and manifest
  author/website/license mismatch (see previous entry - still open,
  product decisions).

## Version 19.0.1.0.0 (2025-07-19) - Initial release (broken on Odoo 19)

### Added
- Initial release for Odoo 19
- 9 financial report types: Balance Sheet, Profit & Loss, Cash Flow Statement, Trial Balance, General Ledger, Partner Ledger, Aged Receivable, Aged Payable, Tax Report
- Raw SQL report engine with high-performance aggregation queries
- XLSX export with xlsxwriter formatting for all 9 reports
- QWeb PDF template with company branding support
- OWL 2.0 interactive frontend widget
- 3-tier access control: User, Manager, Admin
- Configurable account type to financial statement section mapping
- Multi-company support with per-company report configurations
- Period comparison with automatic previous-period calculation
- Configurable aging bucket intervals
- Company-level settings: decimal precision, negative number format, custom header/footer, report logo