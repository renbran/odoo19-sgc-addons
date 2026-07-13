# Construction Reporting Catalog - Phase 1 (Tier 1 Priority)

| Report Name | Owner | Frequency | Source Models | PDF | Excel | Email | Schedule |
|-------------|-------|-----------|---------------|-----|-------|-------|----------|
| **Statement of Account** | Finance | On Demand | `res.partner`, `account.move` | Yes | Yes | Yes | Yes |
| **Customer Ledger** | Finance | Weekly | `res.partner`, `account.move` | Yes | Yes | Yes | Yes |
| **Vendor Ledger** | Finance | Weekly | `res.partner`, `account.move` | Yes | Yes | Yes | Yes |
| **RA Billing Report** | QS / Billing | Monthly | `construction.ra.billing` | Yes | Yes | Yes | No |
| **Interim Payment Certificate (IPC)** | QS / PM | Monthly | `construction.ra.billing` | Yes | Yes | Yes | No |
| **Variation Order (VO) Register** | QS / PM | Weekly | `construction.document` (Category: VO) | Yes | Yes | Yes | Yes |
| **WIP Report** | Finance / PM | Monthly | `construction.project`, `account.move` | Yes | Yes | Yes | Yes |
| **Cost-to-Complete** | PM / Finance | Monthly | `construction.project`, `construction.boq` | Yes | Yes | Yes | No |
| **Cash Flow Forecast** | Finance / PM | Monthly | `construction.project`, `construction.wbs` | Yes | Yes | Yes | Yes |
| **Profitability Report** | Executive | Monthly | `construction.project`, `account.move` | Yes | Yes | Yes | Yes |
| **Project Monthly Progress Report** | PM | Monthly | `construction.site.diary`, `construction.wbs` | Yes | Yes | Yes | Yes |
| **Executive Portfolio Report** | CEO / GM | Monthly | `construction.project` (All) | Yes | Yes | Yes | Yes |

# Phase 2 (Tier 2 Priority)

| Report Name | Owner | Frequency | Source Models | PDF | Excel | Email | Schedule |
|-------------|-------|-----------|---------------|-----|-------|-------|----------|
| **Daily Site Diary** | Site Engineer | Daily | `construction.site.diary` | Yes | No | Yes | No |
| **Weekly Progress Report** | PM | Weekly | `construction.site.diary`, `construction.wbs` | Yes | Yes | Yes | Yes |
| **Material Consumption** | Storekeeper | Weekly | `construction.site.diary`, `stock.move` | Yes | Yes | No | No |
| **Procurement Register** | Procurement | Weekly | `purchase.order`, `construction.project` | Yes | Yes | Yes | Yes |
| **Labor Productivity** | PM | Weekly | `construction.labor.attendance` | Yes | Yes | No | No |
| **Equipment Utilization** | PM | Weekly | `construction.equipment.log` | Yes | Yes | No | No |
| **NCR Register** | QA/QC | Weekly | `construction.quality.check` | Yes | Yes | Yes | Yes |
| **Inspection Register** | QA/QC | Weekly | `construction.quality.check` | Yes | Yes | Yes | Yes |

# Phase 3 (Tier 3 Priority - HSE)

| Report Name | Owner | Frequency | Source Models | PDF | Excel | Email | Schedule |
|-------------|-------|-----------|---------------|-----|-------|-------|----------|
| **HSE Incident Report** | HSE Officer | On Incident | `construction.hse.incident` | Yes | No | Yes | No |
| **Toolbox Talks Register** | HSE Officer | Weekly | `construction.document` (Category: HSE) | Yes | Yes | No | No |
| **Safety Violations** | HSE Officer | Weekly | `construction.hse.incident` | Yes | Yes | Yes | No |
