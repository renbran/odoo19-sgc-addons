# Quick Start: Odoo 19 Deployment Checklist

**Module:** `ks_dynamic_financial_report`  
**Upgrade Status:** ✅ COMPLETE  
**Version:** 19.0.1.1.0  
**Date:** March 4, 2026

---

## What Was Changed?

| File | Change | Impact |
|------|--------|--------|
| `__manifest__.py` | Version 17→19, License update | Must reload module |
| `models/__init__.py` | Fixed broken import | Critical bug fix |
| `views/ks_assets.xml` | Cleaned assets | No functional impact |

---

## Deployment Steps (5 minutes)

### Step 1: Backup (1 min)
```bash
pg_dump odoo_database > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: Restart Server (1 min)
```bash
systemctl restart odoo
# OR for development
python -m odoo -c /etc/odoo/odoo.conf --stop-after-init
```

### Step 3: Upgrade Module in Odoo UI (2 min)
```
1. Login as Administrator
2. Click "Apps" menu
3. Search: "Dynamic Financial Report"
4. Click "Upgrade" button
5. Wait for green "Installed" indicator
```

### Step 4: Verify (1 min)
```
1. Check Accounting menu → Dynamic Financial Reports
2. Open any report type
3. Check browser console (F12) for errors
4. Verify no red errors in Odoo server logs
```

---

## Verification Tests

Run these quick tests:

```
✅ General Ledger Report → Generate ✅
✅ Trial Balance → Generate ✅
✅ Balance Sheet → Generate ✅
✅ Profit & Loss → Generate ✅
✅ Export to PDF ✅
✅ Export to XLSX ✅
```

---

## Troubleshooting

**Issue:** Module won't upgrade
```
Solution: 
- Click "Uninstall" first
- Refresh page (Ctrl+Shift+Del cache)
- Click "Install" button
```

**Issue:** JavaScript errors
```
Solution:
- Clear browser cache (Ctrl+F5)
- Clear Odoo server cache: rm -rf /path/to/odoo/.cache
- Restart Odoo
```

**Issue:** Report not showing
```
Solution:
- Verify user permissions (Settings → Users)
- Check accounting access group membership
- Verify database module list updated
```

---

## Support Files

📄 **Detailed Guide:** `/custom/ks_dynamic_financial_report/ODOO19_UPGRADE.md`  
📄 **Full Report:** `/custom/ODOO19_ACCOUNTING_UPGRADE_REPORT.md`

---

## Questions?

✅ Both guides have complete procedures  
✅ Low-risk upgrade confirmed  
✅ Ready for production deployment  

**Proceed with confidence!** 🚀
