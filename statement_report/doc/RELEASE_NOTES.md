## Module <statement_report>

#### 16.01.2024
#### Version 17.0.1.0.0
#### ADD

- Initial commit for Customer/ Supplier Payment Statement Report

#### 21.05.2026
#### Version 19.0.1.0.0
#### FIX

- Migrated to Odoo 19.0 (no API breaks required)
- Fixed SQL injection: all raw SQL queries now use parameterized psycopg2 placeholders
- Fixed cron methods: `_render_qweb_pdf` now passes `rec` instead of `self` for correct record context
- Updated manifest to version 19.0.1.0.0
