# Construction Management — Outstanding Workflow Gaps & Integration Documentation

**Module:** `aos_construction_management`
**Version:** 19.0.1.0.0 (Odoo 19)
**Reviewed:** 2026-06-21 — full source audit of all models, views, hooks
**Deployment under review:** `test19.tachimao.com`, database `aos_cm`
**Status:** Analysis & proposal — no production code changed by this document

---

## 0. How to read this document

- **Section 1** — what the module is today (architecture map).
- **Section 2** — the **gap register**: every disconnect found, with severity, code evidence, business impact, and fix direction.
- **Section 3** — phased integration roadmap.
- **Section 4** — detailed accounting/invoicing design (the original question).
- **Section 5** — smaller correctness issues found along the way.
- **Section 6** — open questions needing business sign-off.

Severity legend: 🔴 Critical (breaks the core promise) · 🟠 Major · 🟡 Moderate · ⚪ Minor.

---

## 1. Current architecture

### 1.1 Models and relations (as built)

```
construction.project (hub)
├── boq_ids            → construction.boq ──< construction.boq.line (qty × unit_rate)
├── wbs_ids            → construction.wbs (parent/child, progress, planned/actual cost)
├── work_order_ids     → construction.work.order ──< material_requisition_ids
├── material.requisition ──< requisition.line (product_id, qty_req/appr/recv)
├── subcontract_ids    → construction.subcontract (subcontractor = res.partner)
├── quality.check      → ──< quality.checklist
├── expense_ids        → construction.expense (category, amount)
├── ra.billing         → ──< ra.billing.line (qty_prev/current, unit_rate)
└── progress.billing   → (percent_complete → amount_earned)
```

### 1.2 What works today

- Project as central record with smart-button counts (`_compute_counts`).
- BOQ → line amount roll-up (`qty × unit_rate`).
- WBS hierarchy + manual progress; project progress = **simple average** of WBS progress.
- Simple state machines on every document (`draft → … → done`) via button methods.
- OWL dashboard (now fixed) with live KPI counts.
- `mail.thread` chatter/tracking on all documents.
- Sequences for `ref` codes defined in `security/construction_security.xml`.
- BOQ PDF report.

### 1.3 What the dependency list promises but doesn't deliver

`'depends': ['base', 'mail', 'product', 'uom', 'account']`

- `account` — **declared, never used** (no `account.move`, no journal, no analytic). See Gap A.
- `product` — used only on requisition lines; **no purchase/stock**, so products never move through inventory. See Gap C.
- `uom` — used as labels on lines; no UoM conversion logic.

---

## 2. Gap register

### 🔴 Gap A — No accounting / invoicing integration
**Evidence:**
- `construction_billing.py` `progress.billing.action_invoice()` → `self.state = 'invoiced'` (no `account.move`).
- `construction_billing.py` RA billing `action_pay()` → `self.state = 'paid'` (no payment, no reconciliation).
- No `account.move`, `account.move.line`, `account.journal`, or `account.analytic.account` anywhere in the module.

**Impact:** Nothing reaches the General Ledger. Revenue (client billing) and cost (expenses, subcontracts) are tracked only as construction-side numbers; Finance has to re-key everything into Accounting. No AR/AP, no tax, no statutory reporting, no profitability from the GL. `depends['account']` is dead weight.

**Fix:** Generate `out_invoice` from RA/Progress billing, `in_invoice` from expenses/subcontracts, with per-project analytic distribution. Full design in **Section 4**.

---

### 🔴 Gap B — BOQ is disconnected from Billing (no quantity control)
**Evidence:**
- `construction.ra.billing.line.boq_line_description` is a **free-text `Char`** (`construction_billing.py`), not a `Many2one` to `construction.boq.line`.
- `boq_qty` on the billing line is **manually typed**, not pulled from the BOQ.
- No constraint linking cumulative billed qty to BOQ qty.

**Impact (this is core to construction billing):**
- No traceability from a billed item back to its BOQ line.
- **Over-billing risk:** nothing stops `qty_cumulative` exceeding the BOQ contract quantity.
- No "balance quantity to bill" per BOQ item; QS team must reconcile on spreadsheets.
- RA billing cannot be auto-populated from the BOQ — every RA is hand-typed.

**Fix:**
- Add `boq_line_id = Many2one('construction.boq.line')` on `ra.billing.line`; default description/uom/unit_rate/boq_qty from it.
- Add `qty_billed_to_date` (computed across all RA billings) and `qty_balance = boq_qty − qty_billed_to_date` on the BOQ line.
- `@api.constrains` to block `qty_cumulative > boq_qty` (configurable tolerance).
- "Generate RA from BOQ" wizard to seed billing lines.

---

### 🔴 Gap C — Procurement / Inventory not integrated
**Evidence:**
- `construction.material.requisition.action_receive()` → `self.state = 'received'` only.
- `requisition.line` has `product_id`, `qty_received` (manual) but **no `stock.move`, `stock.picking`, or `purchase.order`**.
- Module does not depend on `purchase` or `stock`.

**Impact:** Material flow is paper-only. Approving a requisition does not raise a Purchase Order; receiving does not create a goods receipt or update inventory; consumed materials never hit project cost via stock valuation. `qty_approved`/`qty_received` are honour-system fields.

**Fix (phased):**
- Phase: add `purchase` dep → "Create RFQ/PO" from approved requisition (`purchase.order` per vendor, origin = requisition ref, analytic = project).
- Phase: add `stock` dep → receipts via `stock.picking`; `qty_received` becomes computed from done moves.
- Link delivered cost into project actual cost (see Gap D).

---

### 🔴 Gap D — Actual cost roll-up is broken end-to-end
**Evidence:**
- `construction.work.order.actual_cost` is a **plain manual `Monetary`** (not computed).
- `construction.wbs.actual_cost` = `sum(work_order_ids.actual_cost)` — so WBS cost depends entirely on someone hand-typing each work order's actual cost.
- `material_requisition_ids` are linked to work orders but their `total_estimated_cost` **does not** feed `work_order.actual_cost`.
- `construction.expense` has `wbs_id` but **no `work_order_id`** and does not roll into actual cost.
- No `total_cost` on the project at all.

**Impact:** The cost-control story (plan vs actual, the reason to buy a construction module) does not function. "Actual cost" is a manual number with no source documents behind it. Budget overrun cannot be detected automatically.

**Fix:**
- Make `work_order.actual_cost` computed from linked actuals (requisitions received + labour + expenses tagged to the WO), or — cleaner — derive **all** actual cost from the analytic account (Gap A) so every posted move contributes once.
- Add `work_order_id` to `construction.expense`.
- Add `project.total_cost` and `project.margin = contract_value − total_cost`.
- Add `budget vs actual` per WBS (`planned_cost` already exists).

---

### 🟠 Gap E — Project financial KPIs are incomplete / inconsistent
**Evidence:**
- `project.total_billed` (in `construction_project.py:_compute_financials`) sums **only `ra.billing`** with `state='approved'`. **Progress billing is ignored.**
- No `total_cost`, no margin, no cash position.
- `project.progress` = unweighted average of WBS `progress` — a 1%-value phase counts the same as a 90%-value phase.

**Impact:** Projects billed via Progress Billing show `total_billed = 0`. Dashboard/forms understate revenue. Progress % is misleading for cost/value-weighted reporting.

**Fix:** Include progress billing in `total_billed` (or unify both into invoices and read from `account.move`); weight `progress` by WBS `planned_cost` or BOQ value; add cost/margin computes.

---

### 🟠 Gap F — No labour / HR / timesheet integration
**Evidence:**
- `foreman_id`, `responsible_id`, `inspector_id`, `employee_id` are all `res.users`, **not `hr.employee`**.
- Expense category `labour` exists but there is no labour log, no `hr_timesheet`, no manpower/day record.
- No dependency on `hr` / `hr_timesheet`.

**Impact:** Labour cost (a major construction cost) cannot be captured from timesheets or daily manpower; it can only be entered as a lump-sum expense. No crew/attendance tracking. Site daily reports absent.

**Fix:** Optional `hr_timesheet` integration — timesheets on the project's analytic account feed labour cost; add a Daily Site Report / manpower model if required.

---

### 🟠 Gap G — Subcontract ↔ Expense double-counting; manual payments
**Evidence:**
- `construction.subcontract.amount_paid` is **manual**; `amount_remaining = contract_value − amount_paid`.
- Separately, `construction.expense.category` includes `'subcontract'`.
- No link between a subcontract and its expenses/vendor bills.

**Impact:** Subcontract spend can be counted twice (once on the subcontract, once as a subcontract-category expense). Payments are honour-system. Retention computed but never posted anywhere.

**Fix:** Drive subcontract `amount_paid` from posted vendor bills/payments (Gap A); add a `subcontract.payment` (interim certificate) model that posts `in_invoice`; remove/repurpose the manual field; book retention to a retention account.

---

### 🟠 Gap H — Quality does not gate the work-order lifecycle
**Evidence:**
- `quality.check.work_order_id` exists, but `work.order.action_done()` performs no check on related QC results.
- `result` / `corrective_action` drive no downstream workflow.

**Impact:** A work order can be closed with failed or missing final inspection. Quality is recorded but not enforced — no hold points, no NCR (non-conformance) loop.

**Fix:** Block `work_order.action_done()` when a mandatory `final` QC is not `pass` (configurable); optionally add an NCR/corrective-action workflow with activities.

---

### 🟡 Gap I — No client portal / external visibility
**Evidence:** No `portal`/`website` dependency; no portal mixin on project or billing.

**Impact:** Clients/consultants cannot view project progress or approved billing online; everything is internal. Common ask for construction owners.

**Fix:** Optional `portal` integration exposing project progress and approved RA/Progress billing (and their invoices) to the client contact.

---

### 🟡 Gap J — Thin reporting / documents
**Evidence:** Only a BOQ QWeb report. No RA billing certificate, no progress claim, no cost report. No structured document register (drawings, contracts, permits, RFIs, submittals) — only chatter attachments.

**Impact:** Key construction paperwork (RA certificate, payment certificate, progress claim PDF) must be produced outside the system. No controlled document register.

**Fix:** Add QWeb reports for RA billing certificate and progress claim; optionally a `construction.document` register with revisions/RFIs/submittals.

---

### 🟡 Gap K — Approvals are flag-flips, no controls
**Evidence:** Every `action_*` simply sets `state` with no validation, no approval matrix, no amount thresholds, no scheduled activities.

**Impact:** No segregation of duties; e.g., the same user can submit and approve an expense or RA billing of any size. No audit beyond chatter.

**Fix:** Add approval rules (e.g., expense/RA over a threshold needs a manager group), schedule `mail.activity` on submit, and tighten record rules.

---

## 3. Integration roadmap (recommended order)

| Phase | Theme | Gaps addressed | Value | Risk |
|---|---|---|---|---|
| **1** | Customer invoicing from billing | A (revenue half) | 🔴 high | low — additive |
| **2** | Analytic job costing on project + cost/margin KPIs | A, D, E | 🔴 high | low/med |
| **3** | BOQ↔RA linkage + qty control | B | 🔴 high | med — data model change |
| **4** | Expenses & subcontracts → vendor bills | A (cost half), G | 🟠 | med |
| **5** | Procurement (PO) then Inventory (receipts) | C | 🟠 | med/high — new deps |
| **6** | Labour/timesheets, quality gating, approvals, portal, reports | F, H, I, J, K | 🟡 | varies |

**Recommended first delivery: Phase 1 + 2** — it makes money flow to the GL and turns on real per-project profitability with the smallest, safest surface, and is independently demoable on `aos_cm`.

---

## 4. Detailed design — Accounting / Invoicing (Phases 1, 2, 4)

### 4.1 Customer invoice from RA Billing
```python
# construction.ra.billing
move_id = fields.Many2one('account.move', copy=False, readonly=True)
journal_id = fields.Many2one('account.journal',
    domain="[('type','=','sale')]")
payment_state = fields.Selection(related='move_id.payment_state')

def action_create_invoice(self):
    self.ensure_one()
    if self.move_id:
        return self._open_invoice()
    if not self.project_id.client_id:
        raise UserError(_("Set a Client on the project before invoicing."))
    analytic = self.project_id._get_or_create_analytic()
    journal = self.journal_id or self.env['account.journal'].search(
        [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)], limit=1)
    lines = [(0, 0, {
        'name': l.boq_line_description,
        'quantity': l.qty_current,
        'price_unit': l.unit_rate,
        'analytic_distribution': {str(analytic.id): 100},
    }) for l in self.line_ids]
    move = self.env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': self.project_id.client_id.id,
        'invoice_origin': self.ref or self.name,
        'journal_id': journal.id,
        'currency_id': self.currency_id.id,
        'invoice_line_ids': lines,
    })
    self.write({'move_id': move.id, 'state': 'invoiced'})
    return self._open_invoice()
```
- Add `'invoiced'` to the RA billing Selection (`draft/submitted/approved/invoiced/paid`).
- `paid` becomes computed from `move_id.payment_state == 'paid'`, replacing manual `action_pay`.
- **Retention:** add a negative invoice line (or a dedicated retention receivable account) of `−retention_amount` so the invoice nets to `net_payable`, with retention tracked on the balance sheet until release.

### 4.2 Customer invoice from Progress Billing
Same pattern, one line: `name="Progress Billing %.0f%% — %s" % (percent_complete, project.name)`, `quantity=1`, `price_unit=amount_this_period`. Replaces the current no-op `action_invoice`.

### 4.3 Vendor bills from Expense / Subcontract
```python
# construction.expense
move_id = fields.Many2one('account.move', copy=False, readonly=True)
partner_id = fields.Many2one('res.partner', string='Vendor')

def action_post_to_accounting(self):
    for exp in self.filtered(lambda e: e.state == 'approved' and not e.move_id):
        analytic = exp.project_id._get_or_create_analytic()
        account = exp._expense_account()  # by category or product
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': (exp.partner_id or exp._default_vendor()).id,
            'invoice_origin': exp.ref or exp.name,
            'invoice_line_ids': [(0, 0, {
                'name': exp.name,
                'quantity': 1,
                'price_unit': exp.amount,
                'account_id': account.id,
                'analytic_distribution': {str(analytic.id): 100},
            })],
        })
        exp.write({'move_id': move.id, 'state': 'posted'})
```
- Subcontract: add a `construction.subcontract.payment` (interim payment certificate) that posts an `in_invoice` and feeds `amount_paid`; retention handled like RA billing.

### 4.4 Analytic job costing (Phase 2)
```python
# construction.project
analytic_account_id = fields.Many2one('account.analytic.account', copy=False)
invoice_count = fields.Integer(compute='_compute_account_stats')
vendor_bill_count = fields.Integer(compute='_compute_account_stats')
analytic_revenue = fields.Monetary(compute='_compute_account_stats')
analytic_cost = fields.Monetary(compute='_compute_account_stats')
analytic_margin = fields.Monetary(compute='_compute_account_stats')

def _get_or_create_analytic(self):
    self.ensure_one()
    if not self.analytic_account_id:
        plan = self.env['account.analytic.plan'].search([], limit=1) \
            or self.env['account.analytic.plan'].create({'name': 'Projects'})
        self.analytic_account_id = self.env['account.analytic.account'].create({
            'name': self.name, 'plan_id': plan.id, 'partner_id': self.client_id.id,
        }).id
    return self.analytic_account_id
```
> **Odoo 19 specifics:** analytic accounts require a `plan_id`; move lines carry `analytic_distribution` as a JSON dict `{analytic_id: percent}` (the old `analytic_account_id` M2o on the line is gone). Revenue/cost read from `account.analytic.line` or aggregated posted `account.move.line` filtered by the analytic.

### 4.5 Views / UX
- RA & Progress billing: `Create Invoice` button (state `approved`, no `move_id`) + `View Invoice` smart button + `payment_state`.
- Expense: `Post to Accounting` button + vendor-bill smart button.
- Project: `Invoices` / `Vendor Bills` smart buttons + revenue/cost/margin group.
- Optional `Construction Project` M2o on `account.move` for back-traceability.

### 4.6 Security
Generated moves belong to Accounting. Either require billing users to also hold `account.group_account_invoice`, or create moves via a controlled service method after an explicit access check (avoid blanket `sudo()`). Add `ir.model.access` for any new models (e.g. `construction.subcontract.payment`).

### 4.7 Migration / deployment
- All changes additive → safe `-u aos_construction_management`.
- Adding Selection values is non-destructive; existing `aos_cm` demo rows stay valid.
- Deploy (as this session): edit under `/opt/merged-addons/aos_construction_management/`, then
  `docker-compose exec -T odoo odoo -d aos_cm -u aos_construction_management --stop-after-init`.

### 4.8 Tests
`TransactionCase`: invoice creation (type/partner/lines/analytic), idempotency (`move_id` guard), progress-billing amount, expense→bill, retention netting, dashboard regression, project `total_billed` consistency.

---

## 5. Smaller correctness issues found during audit

| # | Issue | Evidence | Suggested fix |
|---|---|---|---|
| 5.1 | `total_billed` ignores progress billing | `construction_project.py` `_compute_financials` | include progress billing or read from invoices |
| 5.2 | `work_order.actual_cost` manual but feeds WBS cost | `construction_work_order.py`, `construction_wbs.py` | compute from source docs / analytic |
| 5.3 | Verify sequences exist for **all 9** models | `security/construction_security.xml` shows 5 (project, boq, work_order, requisition, subcontract); ra.billing / progress.billing / quality.check / expense call `next_by_code` too | add missing `ir.sequence` records or `ref` stays `'New'` |
| 5.4 | `progress` is unweighted average | `construction_project.py` `_compute_progress` | weight by planned_cost / BOQ value |
| 5.5 | `ra_number` declared `readonly`, never assigned | `construction_billing.py` | auto-increment per project on confirm |
| 5.6 | Sequences live in `security/` file (odd placement) | `construction_security.xml` | move to `data/ir_sequence.xml` for clarity |
| 5.7 | Demo data is demo-flagged → absent on `--without-demo` DBs | `__manifest__.py` `'demo'` | for seeded test envs, load via ORM (done) or enable demo at DB creation |
| 5.8 | `requisition.line.qty_approved/received` unvalidated | `construction_material_requisition.py` | constrain `received ≤ approved ≤ requested`, or derive from stock |

---

## 6. Open questions for business sign-off

1. **Tax** — should generated invoices/bills carry default taxes, or be tax-excluded (reverse-charge/zero-rate common in KSA construction)?
2. **Retention** — post to a dedicated balance-sheet retention account on invoicing, or only track on the construction doc until release?
3. **Line products** — keep free-text billing/requisition lines, or introduce `product_id` per line to properly drive accounts/taxes/UoM?
4. **Procurement depth** — is full Purchase + Inventory in scope, or is requisition-as-record sufficient for now?
5. **Labour** — capture via `hr_timesheet`, via a daily manpower log, or remain lump-sum expense?
6. **Who invoices** — PMs create invoices directly (needs accounting rights) or only flag "ready to invoice" for Finance?
7. **Multi-company** — single company (`aos_cm`) or must per-company journals/sequences be supported?
8. **BOQ control strictness** — hard block over-billing beyond BOQ qty, or warn with override permission?

---

*End of document. No production code has been modified by this analysis. Recommended next step: approve Phase 1 + 2 scope, then implement and verify on `aos_cm`.*
