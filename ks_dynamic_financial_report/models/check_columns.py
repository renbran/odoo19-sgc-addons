#!/usr/bin/env python3
import psycopg2
conn = psycopg2.connect(host="postgres-prod", port=5432, user="odoo", password="odoo", dbname="odoo19-sgc")
c = conn.cursor()

# Check account_account
c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'account_account' AND column_name IN ('code', 'company_id', 'company_ids')")
print("=== account_account ===")
for r in c.fetchall(): print(r)

# Check account_journal
c.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'account_journal' AND column_name IN ('code', 'company_id', 'company_ids')")
print("=== account_journal ===")
for r in c.fetchall(): print(r)

# Check what ks_df_build_where_clause produces - join tables
c.execute("""
    SELECT column_name, data_type FROM information_schema.columns
    WHERE table_name = 'account_account'
    ORDER BY ordinal_position
""")
print("=== All account_account columns ===")
cols = c.fetchall()
for r in cols:
    print(f"  {r[0]}: {r[1]}")

conn.close()
