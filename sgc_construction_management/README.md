# SGC Construction Management

**Odoo 19 module - construction project management suite.**

Authoritative end-to-end management of construction projects: from first BOQ
estimate through WBS, work orders, material requisitions, subcontracts,
quality checks, expenses, all the way to RA / progress billing and finance
integration. Built natively on Odoo 19 with an OWL dashboard and QWeb reports.

## Features

- **Projects** - full lifecycle with auto reference (PROJ-0001), client, contract value, progress bar, 8 smart-button shortcuts.
- **Bill of Quantities (BOQ)** - itemised BOQ with section headers, work types, UOM, rates, auto-computed amounts. Draft -> Approved -> Revised.
- **WBS Phases** - hierarchical Work Breakdown Structure with planned vs actual cost roll-up.
- **Work Orders** - task-level work orders linked to WBS phases with foreman, priority, planned/actual dates, cost tracking, material requisition linkage.
- **Material Requisitions** - Draft -> Approved -> Received with qty requested/approved/received and cost estimation.
- **Subcontracts** - scope, contract value, retention %, amount paid/remaining, activation workflow.
- **RA Billing (Running Account)** - cumulative qty (previous + current), retention withholding, net payable per bill, multi-period history.
- **Progress Billing** - % complete -> earned value -> net this period.
- **Quality Checks** - 5 inspection types, Pass / Fail / Conditional, checklists, corrective action tracking, inspector assignment.
- **Expenses** - categorised (Materials, Labour, Equipment, Subcontract, Overhead) with approval -> vendor bill workflow.
- **Document Management (DMS)** - folders, documents, revisions, transmittals, with category-specific sequences (VO / RFI / NCR / DWG / SUB / IPC).
- **Site Diary** - daily logs with labor attendance, equipment, activities, materials, issues.
- **HSE Incidents** - health / safety / environment incident tracking.
- **OWL Dashboard** - real-time KPIs, revenue vs cost chart, UAE project map, operational backlog.
- **Reports** - QWeb PDF (BOQ, IPC, SOA, WIP, VO Register, Profitability) and XLSX (WIP, RA Billing, Profitability).

## Installation

1. Copy this module into your Odoo 19 `addons` directory.
2. Update the apps list: **Settings -> Apps -> Update Apps List**.
3. Search for "SGC Construction Management" and click **Install**.
4. Demo data (2 projects, BOQs, work orders, billing, expenses) is bundled
   and installs automatically when the database is created with demo data.

## Dependencies

`base`, `mail`, `product`, `uom`, `account`, `report_xlsx`

## Security

5 role levels:

- **User** - read-only access, create draft records
- **Manager** - create and edit, approve requisitions and expenses
- **Administrator** - full CRUD, approve BOQs / billings, manage configuration
- **Project Manager** - project-scoped manager access
- **Finance** - invoice / bill creation, payment state

## License

OPL-1 - USD 149 - see `LICENSE` file.

## Support

- Website: https://sgc-tech.ai
- Email: support@sgc-tech.ai
- Maintainer: SGC TECH AI