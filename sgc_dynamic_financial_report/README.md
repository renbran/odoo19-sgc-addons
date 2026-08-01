# SGC Dynamic Financial Reports

Enterprise-grade dynamic financial reporting suite for Odoo 19 by **SGC TECH AI**.

## Features

### Core Reports
- **9 Report Types**: Balance Sheet, Profit & Loss, Cash Flow, Trial Balance, General Ledger, Partner Ledger, Aged Receivable, Aged Payable, Tax Report
- **Multi-Company**: Per-company configurations, currency settings, and report headers
- **Period Comparison**: Side-by-side comparison with variance analysis
- **Raw SQL Engine**: High-performance aggregation queries for large datasets
- **XLSX Export**: Formatted Excel output with professional styling, freeze panes, and auto-filter
- **PDF Export**: QWeb-based PDF rendering with company branding
- **Hierarchical Display**: Account group hierarchy with expand/collapse indentation
- **Aging Buckets**: Configurable aging intervals for receivable/payable reports
- **Access Control**: 3-tier security (User / Manager / Admin)
- **Account Type Mapping**: Configurable Odoo account type to financial statement section mapping

### Enterprise Uplift Features
- **Multi-Company Consolidated Reporting**: Generate consolidated reports across company hierarchies with automated currency conversion
- **Budget vs Actual Comparison**: Side-by-side columns showing budget, actual, and variance with percentage
- **Drill-Down**: Click through from report line totals to underlying account.move.line records
- **Scheduled Reports**: Configure automated report generation and email delivery via cron
- **Audit Trail**: Immutable snapshots of every generated report with version tracking
- **Analytic Dimension Breakdowns**: Break down financials by analytic account for deeper insight
- **BI API**: Authenticated read-only REST API endpoint for external BI tool integration
- **Polished XLSX**: Professional formatting with zebra striping, auto-sized columns, frozen headers, and page setup

## Installation

1. Copy this directory into your Odoo addons path
2. Ensure `report_xlsx` module is installed (dependency)
3. Update the apps list: `./odoo-bin -c odoo.conf -u sgc_dynamic_financial_report --init-all`
4. Navigate to **Accounting > Reports > SGC Financial Reports**

## Configuration

- **Account Type Mappings**: Settings > SGC Financial Reports > Configuration > Account Type Mappings
- **Company Settings**: Company form > SGC DFR Configuration tab
- **Aging Buckets**: Company form > Aging Bucket Intervals field (default: `0-30,31-60,61-90,91-180,>180`)
- **Budget Targets**: Reports > SGC Budgets > define annual budget with monthly targets per account/company

## Dependencies

- `account`
- `report_xlsx`
- `web`
- `analytic`
- `mail`

## License

OPL-1

## Author

SGC TECH AI — https://sgctech.ai