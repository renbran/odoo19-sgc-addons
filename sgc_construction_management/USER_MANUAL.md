# Construction Management User Manual
## SGC Construction Business Suite — A Day in the Life

**Version:** 2.0 (E2E Workflow Guide)
**Author:** SGC Construction Team
**Date:** June 2026

---

# Table of Contents

### Part I — Welcome
1. [Welcome](#welcome)
2. [Who Uses This System?](#who-uses-this)
3. [The Big Picture: Models & Workflows](#the-big-picture)

### Part II — A Day in the Life: Al Noor Tower Project
- [6:45 AM — Morning Dashboard & Planning](#chapter-1)
- [7:30 AM — Site Briefing & Labor](#chapter-2)
- [8:30 AM — Active Operations](#chapter-3)
- [10:00 AM — Quality & Documentation](#chapter-4)
- [11:30 AM — Incidents & Safety](#chapter-5)
- [1:00 PM — Procurement & Subcontractors](#chapter-6)
- [End of Month — Billing & Payments](#chapter-7)
- [5:00 PM — Wrap Up & Dashboard Review](#chapter-8)

### Part III — Appendices
- [Common Mistakes](#common-mistakes)
- [Glossary](#glossary)
- [FAQ](#faq)
- [Quick Reference: All Models & Menu Locations](#quick-reference)

---

<a name="welcome"></a>
# 1. Welcome

Imagine you're the Project Manager on a 40-storey tower in Dubai. Every day you need to track 200 workers, 15 pieces of heavy equipment, material deliveries, quality inspections, safety briefings, and a mountain of drawings and RFIs. At the end of the month you need to bill your client based on exactly what you built — and if a quality check failed on one floor, that billing should be blocked only for that floor, not the whole project.

This system is built for that reality. It connects **30 models** across **field operations, documentation, quality, safety, equipment, billing, and accounting** — all in one Odoo module.

**This guide doesn't list features in isolation.** It walks through a realistic day on the **Al Noor Tower** project, showing you exactly how each piece connects to the next.

---

<a name="who-uses-this"></a>
# 2. Who Uses This System?

| Role | What They Do |
|---|---|
| **Project Manager** (Ahmed) | Plans the day, signs off site diaries, approves requisitions, submits billing |
| **Site Engineer** (Khalid) | Records site diary, performs quality checks, logs HSE incidents |
| **Foreman** (Rashid) | Assigns workers, tracks hours, reports equipment status |
| **Document Controller** (Fatima) | Manages drawings, RFIs, transmittals, document revisions |
| **Finance / Accounts** (Omar) | Creates invoices from approved billing, pays subcontractor bills |
| **Safety Officer** (Hassan) | Reviews HSE incidents, conducts toolbox talks, closes out investigations |

---

<a name="the-big-picture"></a>
# 3. The Big Picture: Models & Workflows

Here is every data model in the system and how they connect:

```
PROJECT ──┬── BOQ ──┬── RA Billing ──→ Invoice (account.move)
          │         └── Progress Billing ──→ Invoice
          │
          ├── WBS ──┬── Work Orders ──→ Material Requisitions
          │         └── Quality Checks ──→ Quality Checklist Items
          │
          ├── Site Diary ──┬── Activities
          │                ├── Labor Summary
          │                ├── Equipment Summary
          │                ├── Materials Received
          │                └── Issues / Delays
          │
          ├── Equipment ──→ Equipment Logs
          ├── HSE Incidents
          ├── Labor Attendance
          ├── Expenses ──→ Expense Categories
          ├── Subcontracts ──→ Vendor Bill (account.move)
          ├── Documents ──┬── Document Folders
          │               └── Document Revisions
          └── Transmittals ──→ Documents
```

Every model is explained in context below — not as isolated screens, but as steps in your day.

---

<a name="chapter-1"></a>
# Chapter 1 — 6:45 AM: Morning Dashboard & Planning

You're Ahmed. First coffee, then open Odoo.

### 1.1 The Dashboard

Navigate to **Dashboard → Project Dashboard**. This is your command centre:

- **KPI Cards** at the top show: *Total Revenue, Total Expenses, Net Margin, Active Projects*. Green = good, Red = warning.
- **Revenue vs. Cost Chart**: Bar chart comparing what you've billed vs. what you've spent. If expenses are catching up to revenue, you'll see it immediately.
- **UAE Project Map**: Shows pins for every project across Emirates. Click a pin to jump to that project.
- **Operational Backlog sidebar**: Pending Work Orders, open Quality Checks, unapproved Site Diaries — all counted.
- **Quick Sidebar** on the left: One-click links to Projects, BOQs, Invoices, Site Diaries.

![Executive Dashboard](docs/screenshots/01_dashboard.png)
*Figure 1: The Executive Dashboard showing portfolio KPIs, project health matrix, UAE project map, and critical alerts for Al Noor Tower.*

### 1.2 Check Yesterday's Site Diary

1. Click **Site Diary** from the sidebar.
2. Find yesterday's entry for **Al Noor Tower**.
3. Check: Were all activities logged? Any open issues? Was the diary **Approved**?
4. If not approved, review and click **Approve**.

### 1.3 Review Open Work Orders

1. Navigate to **Work Orders**.
2. Filter by project: **Al Noor Tower**, state **Confirmed** or **In Progress**.
3. Review today's planned work:
   - *"L8 Column Rebar Fixing"* — Assigned to Foreman Rashid, planned start today.
   - *"L9 Slab Formwork"* — Waiting for material.
4. Check if any work orders have linked **Material Requisitions** that need approval.

### 1.4 Check Open HSE Incidents

1. Navigate to **HSE Incidents**.
2. Filter **Status = Open**.
3. Review any unresolved incidents from yesterday. Assign investigation if needed.
4. Plan today's **Toolbox Talk** topic.

### 1.5 Review Pending Quality Checks

1. Navigate to **Quality Checks**.
2. Filter **State = Draft or In Progress**.
3. Note which WBS phases need inspection today (e.g., *L8 Column Concrete* needs slump test and cube sampling).

### 1.6 Quick Budget Check

1. Open the **Al Noor Tower** project record.
2. Check **Contract Value** vs. **Expenses to Date**.
3. Review **Subcontract** status — any nearing their limit?

![Projects List](docs/screenshots/05_projects.png)
*Figure 2: Projects list view showing all active construction projects with their budget and completion status.*

---

<a name="chapter-2"></a>
# Chapter 2 — 7:30 AM: Site Briefing & Labor

Time for the morning site briefing. Before work starts, record who's on site.

### 2.1 Record Labor Attendance

The **Labor Attendance** model (`construction.labor.attendance`) tracks daily worker headcount by trade.

1. Go to **Labor Attendance → New**.
2. Select **Project**: Al Noor Tower.
3. Set **Date**: today.
4. Under the lines table, click **Add a line** for each trade:

   | Trade | Regular Hours | Overtime | Workers |
   |---|---|---|---|
   | Steel Fixer | 8 | 0 | 12 |
   | Carpenter | 8 | 2 | 8 |
   | Mason | 8 | 0 | 4 |
   | Electrician | 8 | 0 | 3 |
   | Laborer | 8 | 1 | 10 |
   | Crane Operator | 8 | 0 | 2 |

5. Add a note about the **shift supervisor** in remarks.
6. Click **Save**.

**Why this matters**: Over time, attendance records feed into labor cost tracking. You can compare planned vs. actual hours per project and validate subcontractor invoices.

![Labor Attendance](docs/screenshots/04_labor_attendance.png)
*Figure 3: Labor Attendance form with trade-by-trade headcount entries.*

The **HSE Incident** model (`construction.hse.incident`) logs all safety events — including toolbox talks.

1. Go to **HSE Incidents → New**.
2. Fill in:
   - **Title**: *"Toolbox Talk — Working at Height Awareness"*
   - **Project**: Al Noor Tower
   - **Incident Type**: Toolbox Talk
   - **Severity**: Low
   - **Date/Time**: Now
   - **Description**: *"Delivered 15-minute TBT on proper harness use, ladder safety, and guardrail inspection. 22 workers attended. Questions raised about scaffolding tags — re-assigned for follow-up."*
3. Click **Save** → status remains **Open** until the safety officer closes it.

### 2.3 Assign Work Orders

1. Go to **Work Orders** and open today's first order: *"L8 Column Rebar Fixing"*.
2. Set **Foreman**: Rashid.
3. Set **Actual Start**: today.
4. Click **Start** (changes state from **Confirmed → In Progress**).
5. The work order is now active. The foreman can see it on his dashboard.

**Work Order states**: `Draft → Confirmed → In Progress → Done → Cancelled`. Use **Reset** to go back to Draft.

**Tip**: Material requisitions can be linked to a Work Order via the `material_requisition_ids` One2many field, so you can see what materials are needed for each job.

![Work Orders](docs/screenshots/10_work_orders.png)
*Figure 4: Work Orders list filtered by project showing state, assigned foreman, and linked material requisitions.*

---

<a name="chapter-3"></a>
# Chapter 3 — 8:30 AM: Active Operations

The site is running. Now record everything in the **Site Diary**.

### 3.1 Create Today's Site Diary

The **Site Diary** (`construction.site.diary`) is the central log for the day. It contains five sub-models as tabs:

| Tab | Model | What You Record |
|---|---|---|
| Activities | `construction.site.diary.activity` | What work was done, linked to WBS phases |
| Labor | `construction.site.diary.labor` | Trade-by-trade headcount (planned vs actual) |
| Equipment | `construction.site.diary.equipment` | Machinery used, hours, status |
| Materials | `construction.site.diary.material` | Deliveries received, quantities consumed |
| Issues | `construction.site.diary.issue` | Delays, problems, incidents |

1. Go to **Site Diary → New**.
2. Set **Project**: Al Noor Tower.
3. **Date**: today, **Weather**: Sunny, **Temp**: 42°C, **Shift**: Day.
4. Write a **Summary**: *"L8 column rebar fixing underway. Concrete pour scheduled for tomorrow. Tower crane operational."*
5. Click **Save**.

![Site Diary Form](docs/screenshots/02_site_diary.png)
*Figure 5: Site Diary form with Activities, Labor, Equipment, Materials, and Issues tabs — the central daily log.*

Under the **Activities** tab, add each work package:

1. Click **Add a line**.
2. Select **WBS Phase**: *L8 Columns*.
3. **Description**: *"Rebar fixing and tying for columns L8-A through L8-F"*
4. **Progress %**: 60%
5. Click **Add a line** again:
   - **WBS Phase**: *L8 Columns*
   - **Description**: *"Formwork alignment check for column shutters"*
   - **Progress %**: 30%

Each activity links to a **WBS phase** (`construction.wbs`), which is how progress rolls up to project-level reporting.

![WBS Phases](docs/screenshots/11_wbs_phases.png)
*Figure 6: WBS Phases tree view — the work breakdown structure that rolls progress up to project-level reporting.*

### 3.3 Log Equipment Usage

Under the **Equipment** tab:

1. Click **Add a line**.
2. **Equipment**: Find and select *Tower Crane TC-01* (from `construction.equipment`).
3. **Hours**: 8.
4. **Status**: Working.

The equipment must exist in the **Equipment Register** first (see Chapter 6 for how to add equipment). If it does, selecting it auto-fills the equipment name.

Add a second line for the *Concrete Mixer CM-02* — 4 hours, Working.

### 3.4 Record Materials Received

Under the **Materials** tab:

1. Click **Add a line**.
2. **Material**: Search for *Rebar 20mm* (from Odoo's `product.product` catalogue).
3. **UOM**: Tons.
4. **Received**: 12.5.
5. **Consumed**: 0.

Add concrete: *Ready Mix Grade 45* — 40 m³ received, 40 m³ consumed (poured into L8 columns).

### 3.5 Log Site Issues

Under the **Issues** tab:

1. Click **Add a line**.
2. **Issue Type**: Equipment Failure.
3. **Description**: *"Concrete pump breakdown at 10:30 AM. Repairs estimated 2 hours. Delayed column pour to afternoon."*
4. **Impact Hours**: 2.

Issue types: `Material Delay`, `Labor Shortage`, `Equipment Failure`, `Weather Delay`, `Design/RFI Delay`, `Other`.

### 3.6 Update the Equipment Log Separately

For deeper tracking, the **Equipment Log** (`construction.equipment.log`) records daily usage independently of the site diary:

1. Go to **Equipment Logs → New**.
2. **Equipment**: Tower Crane TC-01.
3. **Project**: Al Noor Tower.
4. **Date**: today.
5. **Hours Utilized**: 8.
6. **Fuel Consumed**: 120 L.
7. Remarks: *"Routine operation. No issues."*

This log accumulates total hours and fuel per equipment item — useful for maintenance scheduling and cost allocation.

---

<a name="chapter-4"></a>
# Chapter 4 — 10:00 AM: Quality & Documentation

Mid-morning is a good time for inspections and paperwork.

### 4.1 Perform a Quality Check

The **Quality Check** model (`construction.quality.check`) tracks inspections with pass/fail/conditional results. Each check contains **Checklist Items** (`construction.quality.checklist`).

1. Go to **Quality Checks → New**.
2. **Name**: *"L8 Column Rebar Inspection"*
3. **Project**: Al Noor Tower.
4. **WBS Phase**: L8 Columns.
5. **Work Order**: *"L8 Column Rebar Fixing"*.
6. **Check Type**: Structural.
7. **Inspector**: Khalid (Site Engineer).
8. **Check Date**: today.

Now add checklist items. Under the **Checklist Items** tab:

| Description | Checked? |
|---|---|
| Rebar spacing verification (max 150mm) | ✅ |
| Lap splice length meets design spec | ✅ |
| Concrete cover adequacy (40mm) | ✅ |
| Tie wire secure at all intersections | ✅ |
| Dowel alignment with L9 columns | ❌ (leave unchecked) |

Click **Start** (changes state to **In Progress**), then mark each item. When ready, click **Pass** or **Fail**.

![Quality Checks](docs/screenshots/08_quality_checks.png)
*Figure 7: Quality Check form with checklist items — each check can block RA billing for that WBS phase on failure.*

**States**: `Draft → In Progress → Completed / Failed`.

**Critical**: If a quality check **fails**, it blocks RA Billing from creating an invoice for that WBS phase. The billing engine checks `_get_blocking_failures()` — failed checks with no WBS phase block the entire project; failed checks on a specific WBS only block billing for that phase.

### 4.2 Manage Documents & Folders

The **Document** system has three models:
- `construction.document.folder` — hierarchical folders (like *Drawings > Structural > Foundation*)
- `construction.document` — the document record with auto-numbering
- `construction.document.revision` — version-controlled file uploads

**Creating a Folder Structure:**

1. Go to **Documents → Folders → New**.
2. **Name**: *Structural Drawings*.
3. **Parent Folder**: *Drawings* (or leave blank for root).
4. **Project**: Al Noor Tower.

Create a few more: *RFIs, Quality Records, Contracts, Correspondence*.

**Uploading a Document with Revision:**

1. Go to **Documents → Documents → New**.
2. **Title**: *"Foundation Structural Drawings — S-001 to S-025"*
3. **Project**: Al Noor Tower.
4. **Folder**: *Structural Drawings*.
5. **Category**: Drawing.
6. Click **Save**. The system generates a **Document Number**: *ALN-DWG-2026-0001*.

Now add the first revision:
1. Under **Revisions**, click **Add**.
2. **Revision No.**: *0* (or *A* — your choice).
3. **Status**: Issued for Construction.
4. **Attachment**: Upload the PDF.
5. **Prepared By**: Fatima (auto-filled).
6. Click **Save**. This revision becomes the **Current Revision** on the document.

To issue a new version:
1. Click **Add** again under Revisions.
2. **Revision No.**: *1*.
3. **Status**: Issued for Construction.
4. **Attachment**: Upload the updated PDF.
5. The **Current Revision** auto-updates to point to the latest.

**Document status workflow**: `Draft → Issued → Reviewed → Approved → Closed`.

### 4.3 Send a Transmittal

When sending documents to the client or consultant, use a **Transmittal** (`construction.transmittal`).

1. Go to **Transmittals → New**.
2. **Subject**: *"Structural Drawings S-001 to S-025 — IFC Set"*
3. **Project**: Al Noor Tower.
4. **Recipient**: *Al Noor Properties* (a `res.partner` — the client).
5. **Issue Date**: today.
6. Under **Documents Included**, add the documents you're sending (select the document records created above).
7. Click **Save**.

Then click **Issue**. This:
- Changes transmittal state to **Issued**
- Sets each linked document's status to **Issued**
- Links the transmittal to each document

When the client acknowledges, click **Receive** → **Acknowledge**. States: `Draft → Issued → Received → Acknowledged`.

![Documents List](docs/screenshots/16_documents.png)
*Figure 8: Documents list view showing auto-numbered documents with revision status and folder hierarchy.*
![Transmittals](docs/screenshots/17_transmittals.png)
*Figure 9: Transmittal form — used to send documents to the client or consultant.*

---

<a name="chapter-5"></a>
# Chapter 5 — 11:30 AM: Incidents & Safety

Something happened. A worker slipped on the L8 deck.

### 5.1 Log an HSE Incident

1. Go to **HSE Incidents → New**.
2. **Title**: *"Slip/Trip on L8 Deck — Minor Injury"*
3. **Project**: Al Noor Tower.
4. **Date/Time**: now.
5. **Incident Type**: First Aid.
6. **Severity**: Low.
7. **Description**: *"Worker Ahmed K. slipped on formwork oil spill on L8 deck. Colleagues assisted him to first aid station. Minor abrasion on right forearm — cleaned, dressed. No further treatment required."*
8. **Root Cause / Immediate Actions**: *"Spill was from earlier formwork oil application. Area cleaned immediately, warning signs posted."*
9. **Corrective Action**: *"All work crews reminded to clean oil spills immediately. Additional spill kits placed on L8 and L9 decks."*
10. **Reported By**: Khalid (auto-filled).
11. Click **Save**.

**Incident Types**: Near Miss, First Aid, Lost Time Injury (LTI), Safety Violation, Toolbox Talk, Safety Inspection.

**Severity**: Low, Medium, High, Critical.

**Status**: `Open → Under Investigation → Closed`.

The Safety Officer (Hassan) will review, potentially set to **Under Investigation**, and finally **Close**.

**Attachments**: Use the **Attachments** tab to add photos of the scene or the first aid report.

![HSE Incidents](docs/screenshots/09_hse_incidents.png)
*Figure 10: HSE Incident form showing incident type, severity, description, and corrective actions.*

### 5.2 Record a Safety Inspection

On Fridays, do a formal safety walk:

1. **HSE Incidents → New**.
2. **Type**: Safety Inspection.
3. **Title**: *"Weekly Safety Walk — L8 to L12 Floors"*
4. **Description**: *"Inspected scaffold tags, guardrails, electrical cabling, fire extinguishers, and housekeeping across L8-L12. Found two expired extinguishers on L10 — replaced immediately. One unguarded edge on L11 stair opening — barricaded on site."*
5. Click **Save**, set status to **Closed** after corrective actions are verified.

---

<a name="chapter-6"></a>
# Chapter 6 — 1:00 PM: Procurement & Subcontractors

After lunch, it's time to order materials and track subs.

### 6.1 Create a Material Requisition

The **Material Requisition** model (`construction.material.requisition`) manages requests from the field. Each line is a `construction.material.requisition.line`.

1. Go to **Material Requisitions → New**.
2. **Project**: Al Noor Tower.
3. **Work Order**: *L9 Slab Formwork* (link to the work order that needs these materials).
4. **Required Date**: tomorrow.

Add lines:

| Material (product.product) | Quantity | UOM |
|---|---|---|
| Plywood 18mm | 50 | Sheets |
| Timber 4x2 | 200 | LM |
| Scaffold Clamps | 100 | Pcs |
| Nails 4" | 25 | Kg |

5. Click **Submit** to send for approval.
6. A manager reviews and clicks **Approve**.
7. When material arrives on site, click **Receive** to mark quantities received.
8. **Warning**: You cannot "Receive" more than was "Approved" per line.

**States**: `Draft → Submitted → Approved → Received → Done`. Each receipt can be partial.

![Material Requisitions](docs/screenshots/12_material_requisitions.png)
*Figure 11: Material Requisition form with line items for plywood, timber, and scaffold clamps linked to a Work Order.*

### 6.2 Register New Equipment

If a new machine arrived on site:

1. Go to **Equipment → New**.
2. **Name**: *Concrete Boom Pump BP-01*.
3. **Code**: *BP-01*.
4. **Category**: Heavy Equipment.
5. **Status**: Operational.
6. **Project**: Al Noor Tower.
7. Click **Save**.

The equipment is now available in site diary equipment lists and equipment logs.

![Equipment Register](docs/screenshots/03_equipment.png)
*Figure 12: Equipment register showing all machinery with status, category, and assigned project.*

**Equipment statuses**: `Operational`, `Under Maintenance`, `Breakdown`, `Idle`. Changes are tracked via `mail.thread` (chatter).

### 6.3 Track a Subcontract

You hired *Gulf Electrical LLC* for all MEP work. The **Subcontract** model (`construction.subcontract`) tracks this.

1. Go to **Subcontracts → New**.
2. **Name**: *MEP Works Package — Al Noor Tower*
3. **Project**: Al Noor Tower.
4. **Subcontractor**: Gulf Electrical LLC.
5. **WBS Phase**: MEP Works.
6. **Contract Value**: AED 2,500,000.
7. **Retention %**: 10%.
8. **Start Date**: project start.
9. **End Date**: project end.
10. Click **Save**, then **Activate**.

**States**: `Draft → Active → Bill Created → Posted → Completed → Terminated`.

![Subcontracts](docs/screenshots/13_subcontracts.png)
*Figure 13: Subcontract form showing contract value, retention, and status for MEP works.*

When Gulf Electrical sends their monthly invoice:
1. Open the subcontract.
2. Click **Create Bill**. This generates a **Vendor Bill** (`account.move`, type `in_invoice`) with retention deducted.
3. The Finance team posts the bill.
4. As payments are made, update **Amount Paid** (the system tracks `amount_remaining` automatically).

### 6.4 Record an Expense

Daily expenses — site fuel, office supplies, permits:

1. Go to **Expenses → New**.
2. **Description**: *"Diesel for Tower Crane TC-01 — 500L"*
3. **Project**: Al Noor Tower.
4. **Category**: Equipment Fuel (`construction.expense.category`).
5. **Amount**: AED 1,250.
6. **Vendor**: ADNOC Station.
7. Click **Save** then **Approve**.

Expense categories are managed at **Expenses → Categories**. Create: *Equipment Fuel, Site Consumables, Permits, Travel, Accommodation, Subcontractor Services*.

![Expenses](docs/screenshots/07_expenses.png)
*Figure 14: Expenses list view showing daily operational costs categorized by type.*

**Tip**: Always record expenses the same day. Your dashboard profit calculations depend on accurate expense data.

---

<a name="chapter-7"></a>
# Chapter 7 — End of Month: Billing & Payments

The most important day of the month. You need to bill the client for work completed.

### 7.1 Create RA Billing Application

**RA Billing** (`construction.ra.billing`) is quantity-based billing against your BOQ.

![Bill of Quantities](docs/screenshots/06_boq.png)
*Figure 16: Bill of Quantities (BOQ) showing line items with quantities, unit rates, and total amounts.*

1. Go to **RA Billing → New**.
2. **Name**: *"RA Bill No. 3 — Al Noor Tower"*
3. **Project**: Al Noor Tower.
4. **Billing Period**: June 1 — June 30.
5. **Retention %**: 5% (as per contract).
6. Click **Load BOQ Lines**. The system pulls in every BOQ line from your approved BOQ.
7. For each line, enter the **Current Qty** — what you completed this month:

   | BOQ Item | BOQ Qty | Prev. Qty | Current Qty | Unit Rate | Amount |
   |---|---|---|---|---|---|
   | Concrete L8 Columns | 120 m³ | 60 | 40 | AED 850 | AED 34,000 |
   | Rebar L8 Columns | 15 T | 7 | 5 | AED 4,200 | AED 21,000 |
   | Formwork L8 | 500 m² | 250 | 200 | AED 95 | AED 19,000 |

   The system calculates:
   - **Total Amount**: AED 74,000
   - **Net Amount** (minus previous billing): AED 37,000
   - **Retention Amount** (5%): AED 1,850
   - **Net Payable**: AED 35,150

8. Click **Submit**.

![RA Billing](docs/screenshots/14_ra_billing.png)
*Figure 15: RA Billing form with BOQ lines loaded — current quantities, unit rates, and calculated amounts.*

### 7.2 Approval & Quality Gate

1. The manager reviews and clicks **Approve** (state → **Approved**).
2. Click **Create Invoice**.

**The Quality Gate**: Before creating the invoice, the system checks `_get_blocking_failures()`. If any quality checks are **Failed** on the WBS phases being billed, the system blocks the invoice:

> *"Cannot create invoice: blocked by failed quality check(s): L8 Column Rebar Inspection"*

You must fix the quality issue first — re-inspect, pass the check, or create a corrective action plan. This ensures you never bill for defective work.

### 7.3 Finance Creates the Invoice

Once the invoice is created:
1. A **Draft Customer Invoice** (`account.move`, type `out_invoice`) is created.
2. The Finance team (Omar) reviews it:
   - Check the **Analytic Account** is correctly assigned.
   - Verify the **Retention Deduction** line is negative.
3. Click **Confirm / Post**.
4. State becomes **Posted** (or **Invoice Created** if not yet posted).
5. When the client pays, state advances to **Paid**.

### 7.4 Progress Billing (Alternative)

If your contract pays by % complete instead of measured quantities:

![Progress Billing](docs/screenshots/15_progress_billing.png)
*Figure 17: Progress Billing form with percentage completion and calculated amounts.*

1. Go to **Progress Billing → New**.
2. **Name**: *"Progress Payment — June"*
3. **% Complete**: 35%.
4. The system calculates **Amount Earned** = Contract Value × 35%.
5. Enter **Amount Previously Billed**.
6. **Amount This Period** = Earned − Previously Billed.
7. Click **Approve → Create Invoice**.

Progress Billing also has a quality gate, but it checks for ANY failed check on the project (not WBS-scoped).

### 7.5 Payment Follow-Up

Back on the RA Billing record:
- You can click **View Invoice** to jump to the accounting entry.
- The **Payment Status** field shows if the client has paid.
- Once paid, the state updates to **Paid** automatically via the related `account.move`.

---

<a name="chapter-8"></a>
# Chapter 8 — 5:00 PM: Wrap Up & Dashboard Review

End of day. Close everything out.

### 8.1 Complete and Submit the Site Diary

1. Open today's **Site Diary** for Al Noor Tower.
2. Check all tabs are filled: Activities, Labor, Equipment, Materials, Issues.
3. Add **Progress Photos** (drag and drop images into the Photos field).
4. Add any final **Remarks**.
5. Click **Submit**. The diary is now pending approval.
6. A supervisor reviews and clicks **Approve** to lock the entry.

Once approved, the diary feeds data into project progress reports and dashboards. It cannot be edited after approval.

### 8.2 Review the Dashboard

1. Go to **Dashboard → Project Dashboard**.
2. Refresh and check today's impact:
   - **Revenue vs. Cost**: Did today's expenses move the needle?
   - **Operational Backlog**: Did you close any work orders or quality checks?
   - **Active Projects**: Any red flags?

### 8.3 Plan Tomorrow

1. Create **Work Orders** for tomorrow's tasks in **Draft** state.
2. If materials will be needed, create a **Material Requisition** so procurement has time.
3. Schedule the next **Quality Check** — set the date and assign an inspector.
4. Note any pending **HSE Incidents** that need follow-up.

### 8.4 Daily Checklist Summary

| ✅ | Time | Task | Model |
|---|---|---|---|
| ☐ | 6:45 AM | Check dashboard, review yesterday | Dashboard, Site Diary |
| ☐ | 7:30 AM | Record labor attendance | `labor.attendance` |
| ☐ | 7:30 AM | Hold toolbox talk | `hse.incident` |
| ☐ | 7:45 AM | Assign work orders | `work.order` |
| ☐ | 8:30 AM | Create site diary | `site.diary` |
| ☐ | 9:00 AM | Log activities, equipment, materials | `site.diary.*` |
| ☐ | 10:00 AM | Quality inspection | `quality.check`, `quality.checklist` |
| ☐ | 10:30 AM | Document revisions & transmittals | `document`, `transmittal` |
| ☐ | 11:30 AM | HSE incidents | `hse.incident` |
| ☐ | 1:00 PM | Material requisitions | `material.requisition` |
| ☐ | 1:30 PM | Equipment log | `equipment.log` |
| ☐ | 2:00 PM | Expenses | `expense` |
| ☐ | EOM | RA billing | `ra.billing` |
| ☐ | 5:00 PM | Submit site diary, review dashboard | `site.diary`, Dashboard |

---

<a name="common-mistakes"></a>
# Common Mistakes

| # | Mistake | Why It Hurts | Fix |
|---|---|---|---|
| 1 | Billing 110 walls when BOQ has 100 | System blocks it — but you still wasted time | Revise BOQ first or get a variation order approved |
| 2 | Forgetting to record expenses | Dashboard shows inflated profit; real P&L is wrong | Record every receipt daily — even small ones |
| 3 | Ignoring a failed quality check | Blocks invoice creation — you can't get paid | Fix the issue, re-inspect, and pass the check |
| 4 | Not logging HSE incidents immediately | Details get lost; regulatory risk | Log within the hour — even near misses |
| 5 | Submitting transmittals without document revisions | Client receives wrong drawing version | Always attach the latest revision to a transmittal |
| 6 | Not closing site diaries daily | Backlog grows; data doesn't feed reports | Submit and approve by end of each day |
| 7 | Entering wrong labor counts in attendance | Labour cost reports are unreliable | Count heads at morning briefing, not from memory |
| 8 | Using equipment without logging hours | Missed maintenance intervals, wrong cost allocation | Log every machine daily in Equipment Logs |
| 9 | Skipping material receipts in site diary | No record of what arrived vs. what was ordered | Log deliveries as they happen — not end of week |
| 10 | Creating RA billing without Load BOQ Lines | Manual entry errors, missing BOQ items | Always click **Load BOQ Lines** first |

---

<a name="glossary"></a>
# Glossary

| Term | Definition |
|---|---|
| **BOQ** | Bill of Quantities — the complete list of work items, quantities, and rates in a contract |
| **BOQ Line** | A single line item in the BOQ (e.g., "Concrete L8 Columns — 120 m³") |
| **WBS** | Work Breakdown Structure — breaking a project into phases (L8 Columns, L9 Slab, etc.) |
| **Work Order** | A specific task assigned to a crew/foreman (e.g., "Fix rebar on L8 columns") |
| **RA Billing** | Running Account billing — payment based on measured quantities completed |
| **Progress Billing** | Payment based on % completion of the whole project |
| **Retention** | % of payment held back by the client until project completion (usually 5-10%) |
| **Site Diary** | Daily log of site conditions, activities, labor, equipment, materials, and issues |
| **HSE** | Health, Safety & Environment |
| **Near Miss** | An incident that could have caused injury but didn't |
| **LTI** | Lost Time Injury — an injury causing a worker to miss work |
| **Toolbox Talk** | A short daily safety briefing (typically 10-15 minutes) |
| **RFI** | Request for Information — a formal question to the designer/consultant |
| **NCR** | Non-Conformance Report — issued when work doesn't meet specifications |
| **Transmittal** | Cover sheet when sending documents to an external party (client, consultant) |
| **Revision** | A version of a document (0/A/B or 1/2/3) — each revision is stored permanently |
| **Material Requisition** | A formal request to purchase/deliver materials to site |
| **Subcontract** | A contract with a third-party company to perform specific works |
| **Expense Category** | Classification of costs (Equipment Fuel, Site Consumables, Permits, etc.) |
| **Analytic Account** | A tagged account in Odoo Accounting that tracks all costs/revenue for one project |
| **Quality Check** | An inspection with pass/fail result that can block billing if failed |
| **Checklist Item** | One item within a quality check (e.g., "Rebar spacing ≤ 150mm") |
| **Dashboard** | The project command centre with KPIs, charts, maps, and backlog counts |
| **Account Move** | Odoo's universal journal entry — used for both customer invoices and vendor bills |

---

<a name="faq"></a>
# FAQ

**Q: Can I change a project name after starting?**
A: Yes. The analytic account is linked by ID, not name, so all financial history stays intact.

**Q: Why can't I see the "Create Invoice" button on RA Billing?**
A: Only Finance users have access. Ask Omar to help. Also check that no failed quality checks are blocking.

**Q: What if I finish the project early?**
A: Close all work orders, approve the final site diary, complete subcontracts, release retention, and set the project state to **Completed**.

**Q: How do I release retention to a subcontractor?**
A: Open the subcontract, create a final bill with zero retention, post it, and mark the subcontract **Completed**.

**Q: Can I add photos to a site diary?**
A: Yes. Drag and drop images into the **Progress Photos** field (a Many2many to `ir.attachment`).

**Q: What happens if I edit an approved site diary?**
A: You can't — approved diaries are locked. Use **Reset to Draft** to make changes, then re-submit.

**Q: How do I know which quality checks are blocking my billing?**
A: When you click **Create Invoice**, the error message lists every failed check by name. Fix those first.

**Q: Can I partially receive a material requisition?**
A: Yes. When you click **Receive**, enter the partial quantity. The remaining balance stays open until fully received.

**Q: How does the equipment log differ from site diary equipment?**
A: The site diary records what equipment was used on a given day for context. The Equipment Log is a separate dedicated model for tracking hours, fuel, and costs per machine over time.

**Q: What if I need a new expense category?**
A: Go to **Expenses → Categories** and create it. New categories are available immediately in expense records.

---

<a name="quick-reference"></a>
# Quick Reference: All Models & Menu Locations

| # | Model | Technical Name | Menu Path | Covered In |
|---|---|---|---|---|
| 1 | Project | `construction.project` | Projects → Projects | Chapter 1 |
| 2 | BOQ | `construction.boq` | BOQ → BOQs | Chapter 7 |
| 3 | BOQ Line | `construction.boq.line` | (inline in BOQ) | Chapter 7 |
| 4 | WBS Phase | `construction.wbs` | WBS → WBS Phases | Chapter 3 |
| 5 | Work Order | `construction.work.order` | Work Orders → Work Orders | Chapter 2 |
| 6 | Material Requisition | `construction.material.requisition` | Requisitions → Material Requisitions | Chapter 6 |
| 7 | Material Requisition Line | `construction.material.requisition.line` | (inline in requisition) | Chapter 6 |
| 8 | RA Billing | `construction.ra.billing` | Billing → RA Billing | Chapter 7 |
| 9 | RA Billing Line | `construction.ra.billing.line` | (inline in RA billing) | Chapter 7 |
| 10 | Progress Billing | `construction.progress.billing` | Billing → Progress Billing | Chapter 7 |
| 11 | Quality Check | `construction.quality.check` | Quality → Quality Checks | Chapter 4 |
| 12 | Quality Checklist Item | `construction.quality.checklist` | (inline in quality check) | Chapter 4 |
| 13 | Site Diary | `construction.site.diary` | Site Diary → Site Diaries | Chapter 3 |
| 14 | Site Diary Activity | `construction.site.diary.activity` | (inline in diary) | Chapter 3 |
| 15 | Site Diary Labor | `construction.site.diary.labor` | (inline in diary) | Chapter 3 |
| 16 | Site Diary Equipment | `construction.site.diary.equipment` | (inline in diary) | Chapter 3 |
| 17 | Site Diary Material | `construction.site.diary.material` | (inline in diary) | Chapter 3 |
| 18 | Site Diary Issue | `construction.site.diary.issue` | (inline in diary) | Chapter 3 |
| 19 | Document Folder | `construction.document.folder` | Documents → Folders | Chapter 4 |
| 20 | Document | `construction.document` | Documents → Documents | Chapter 4 |
| 21 | Document Revision | `construction.document.revision` | (inline in document) | Chapter 4 |
| 22 | Transmittal | `construction.transmittal` | Transmittals → Transmittals | Chapter 4 |
| 23 | Equipment | `construction.equipment` | Equipment → Equipment | Chapter 6 |
| 24 | Equipment Log | `construction.equipment.log` | Equipment → Equipment Logs | Chapter 3 |
| 25 | HSE Incident | `construction.hse.incident` | HSE → Incidents | Chapters 2, 5 |
| 26 | Labor Attendance | `construction.labor.attendance` | Labor → Attendance | Chapter 2 |
| 27 | Expense | `construction.expense` | Expenses → Expenses | Chapter 6 |
| 28 | Expense Category | `construction.expense.category` | Expenses → Categories | Chapter 6 |
| 29 | Subcontract | `construction.subcontract` | Subcontracts → Subcontracts | Chapter 6 |
| 30 | Invoice / Bill | `account.move` | Accounting → Invoices / Bills | Chapter 7 |

---

**Enjoy building with SGC Construction Management.**
