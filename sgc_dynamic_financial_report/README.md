# SGC Dynamic Financial Reports

Enterprise-grade dynamic financial reporting suite for Odoo 19 by **SGC TECH AI**.

## Features

- **9 Report Types**: Balance Sheet, Profit & Loss, Cash Flow, Trial Balance, General Ledger, Partner Ledger, Aged Receivable, Aged Payable, Tax Report
- **Multi-Company**: Per-company configurations, currency settings, and report headers
- **Period Comparison**: Side-by-side comparison with variance analysis
- **Raw SQL Engine**: High-performance aggregation queries for large datasets
- **XLSX Export**: Formatted Excel output for all 9 reports via xlsxwriter
- **PDF Export**: QWeb-based PDF rendering with company branding
- **Hierarchical Display**: Account group hierarchy with expand/collapse indentation
- **Aging Buckets**: Configurable aging intervals for receivable/payable reports
- **Access Control**: 3-tier security (User / Manager / Admin)
- **Account Type Mapping**: Configurable Odoo account type to financial statement section mapping

## Installation

1. Copy this directory into your Odoo addons path
2. Ensure `report_xlsx` module is installed (dependency)
3. Update the apps list: `./odoo-bin -c odoo.conf -u sgc_dynamic_financial_report --init-all`
4. Navigate to **Accounting > Reports > SGC Financial Reports**

## Configuration

- **Account Type Mappings**: Settings > SGC Financial Reports > Configuration > Account Type Mappings
- **Company Settings**: Company form > SGC DFR Configuration tab
- **Aging Buckets**: Company form > Aging Bucket Intervals field (default: `0-30,31-60,61-90,91-180,>180`)

## Dependencies

- `account`
- `report_xlsx`
- `web`
- `analytic`

## License

OPL-1

## Author

SGC TECH AI — https://sgctech.ai