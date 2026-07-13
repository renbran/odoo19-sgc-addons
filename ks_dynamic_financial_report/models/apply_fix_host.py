fp = '/opt/odoo-prod/extra-addons/ks_dynamic_financial_report/models/ks_dynamic_financial_report_base.py'
with open(fp) as f:
    c = f.read()

changes = []

# Fix 1: L4825
old1 = "self.env['account.account'].search([('company_id', 'in', [self.env.company.id])],"
new1 = "self.env['account.account'].search([('company_ids', 'in', [self.env.company.id])],"
assert old1 in c, 'Fix 1 not found'
c = c.replace(old1, new1)
changes.append('L4825: ks_fetch_account_filters search domain')

# Fix 2: L522
old2 = "ks_accounts = self.env['account.account'].sudo().search(\n                            [('company_id', 'in', ks_df_informations.get('company_ids')),\n                             ('ks_cash_flow_category', 'not in', [0])])"
new2 = "ks_accounts = self.env['account.account'].sudo().search(\n                            [('company_ids', 'in', ks_df_informations.get('company_ids')),\n                             ('ks_cash_flow_category', 'not in', [0])])"
assert old2 in c, 'Fix 2 not found'
c = c.replace(old2, new2)
changes.append('L522: cash flow account search domain')

# Fix 3: L1364
old3 = "ks_df_account_company_domain = [('company_id', 'in', ks_df_informations.get('company_ids'))]"
new3 = "ks_df_account_company_domain = [('company_ids', 'in', ks_df_informations.get('company_ids'))]"
assert old3 in c, 'Fix 3 not found'
c = c.replace(old3, new3)
changes.append('L1364: ks_df_where_clause search domain')

# Fix 4: L2248
old4 = "self.env['account.account'].sudo().search([('company_id', 'in', enabled_company_ids)])"
new4 = "self.env['account.account'].sudo().search([('company_ids', 'in', enabled_company_ids)])"
assert old4 in c, 'Fix 4 not found'
c = c.replace(old4, new4)
changes.append('L2248: trial balance search domain')

# Fix 5: L1189
old5 = "            ks_company_id = ks_account.company_id"
new5 = "            ks_company_id = self.env.company"
assert old5 in c, 'Fix 5 not found'
c = c.replace(old5, new5)
changes.append('L1189: ks_account.company_id attribute access -> self.env.company')

with open(fp, 'w') as f:
    f.write(c)

print(f'Applied {len(changes)} fixes:')
for ch in changes:
    print(f'  OK {ch}')
