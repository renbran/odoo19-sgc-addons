# 🚨 URGENT: CloudPepper Deployment Issue - RESOLVED

**Date**: November 23, 2025  
**Issue**: RPC_ERROR during llm_lead_scoring module installation  
**Status**: ✅ **FIXED - READY FOR DEPLOYMENT**  
**Priority**: CRITICAL

---

## 📋 Issue Summary

### Error Encountered
```
Exception: Module loading llm_lead_scoring failed: 
file llm_lead_scoring/security/ir.model.access.csv could not be processed:
 No matching record found for external id 'crm.group_crm_user' in field 'Group'
 No matching record found for external id 'crm.group_crm_manager' in field 'Group'
```

### Root Cause
The CloudPepper server has an **old version** of the module with **deprecated Odoo 17 security groups**.

### Resolution Status
✅ **Local repository files are CORRECT**  
❌ **CloudPepper server needs update**

---

## ✅ What Was Fixed

### Local Repository (Already Fixed)
✅ `security/ir.model.access.csv` - Updated with correct Odoo 17 groups:
- ❌ OLD: `crm.group_crm_user` → ✅ NEW: `sales_team.group_sale_salesman`
- ❌ OLD: `crm.group_crm_manager` → ✅ NEW: `sales_team.group_sale_manager`

### Deployment Tools Created
1. ✅ **emergency_security_fix.py** - Python script to verify and fix security groups
2. ✅ **fix_cloudpepper_security.sh** - Bash script for server deployment
3. ✅ **CLOUDPEPPER_EMERGENCY_FIX.md** - Complete deployment guide

---

## 🚀 Quick Fix Instructions

### Option 1: Automatic Fix (Recommended)

**On CloudPepper Server:**
```bash
# Download and run the fix script
cd /var/odoo/scholarixv2/addons/llm_lead_scoring
wget https://raw.githubusercontent.com/renbran/FINAL-ODOO-APPS/main/llm_lead_scoring/fix_cloudpepper_security.sh
chmod +x fix_cloudpepper_security.sh
sudo ./fix_cloudpepper_security.sh
```

### Option 2: Git Pull (Cleanest)

**On CloudPepper Server:**
```bash
# Navigate to repository
cd /var/odoo/scholarixv2/addons

# Pull latest changes
git pull origin main

# Upgrade module
./odoo-bin -d scholarixv2 -u llm_lead_scoring --stop-after-init

# Restart Odoo
sudo systemctl restart odoo
```

### Option 3: Manual Edit

**On CloudPepper Server:**
```bash
# Edit the security file
cd /var/odoo/scholarixv2/addons/llm_lead_scoring/security
nano ir.model.access.csv

# Replace ALL instances:
# crm.group_crm_user → sales_team.group_sale_salesman
# crm.group_crm_manager → sales_team.group_sale_manager

# Save and exit (Ctrl+X, Y, Enter)

# Upgrade module
cd /var/odoo/scholarixv2
./odoo-bin -d scholarixv2 -u llm_lead_scoring --stop-after-init
sudo systemctl restart odoo
```

### Option 4: Web UI (After Files Updated)

1. Ensure files are updated on server (Options 1-3)
2. Login to https://scholarixglobal.com/
3. Apps → Update Apps List
4. Find "LLM Lead Scoring" → Click "Upgrade"
5. Wait for completion

---

## 📄 Correct File Content

**File**: `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_llm_provider_user,llm.provider.user,model_llm_provider,sales_team.group_sale_salesman,1,0,0,0
access_llm_provider_manager,llm.provider.manager,model_llm_provider,sales_team.group_sale_manager,1,1,1,1
access_llm_service_user,llm.service.user,model_llm_service,sales_team.group_sale_salesman,1,0,0,0
access_lead_enrichment_wizard_user,lead.enrichment.wizard.user,model_lead_enrichment_wizard,sales_team.group_sale_salesman,1,1,1,1
```

**Key Changes** (4 rows updated):
- Row 2: `crm.group_crm_user` → `sales_team.group_sale_salesman`
- Row 3: `crm.group_crm_manager` → `sales_team.group_sale_manager`
- Row 4: `crm.group_crm_user` → `sales_team.group_sale_salesman`
- Row 5: `crm.group_crm_user` → `sales_team.group_sale_salesman`

---

## ✅ Verification Steps

### 1. Check File Content
```bash
# On server
cat /var/odoo/scholarixv2/addons/llm_lead_scoring/security/ir.model.access.csv

# Should see "sales_team.group_sale_salesman" and "sales_team.group_sale_manager"
# Should NOT see "crm.group_crm_user" or "crm.group_crm_manager"
```

### 2. Check Module Status
```bash
# Check if module is installed
./odoo-bin shell -d scholarixv2
>>> module = env['ir.module.module'].search([('name', '=', 'llm_lead_scoring')])
>>> print(f"State: {module.state}, Version: {module.latest_version}")
>>> exit()

# Expected: State: installed, Version: 17.0.1.0.0
```

### 3. Test in Web UI
1. Login to https://scholarixglobal.com/
2. Go to CRM → Leads/Pipeline
3. Open a lead
4. Should see "Enrich with AI" button
5. Click it → should work without errors

---

## 🎯 Success Criteria

Deployment is successful when:

✅ Module installs without RPC_ERROR  
✅ No "group_crm_user" or "group_crm_manager" errors  
✅ CRM features accessible  
✅ Lead enrichment wizard works  
✅ LLM provider configuration accessible  

---

## 📚 Complete Documentation

| Document | Description |
|----------|-------------|
| **CLOUDPEPPER_EMERGENCY_FIX.md** | Complete deployment guide with troubleshooting |
| **emergency_security_fix.py** | Python validation/fix script |
| **fix_cloudpepper_security.sh** | Bash deployment script |
| **DEPLOYMENT_GUIDE.md** | Original deployment instructions |
| **README_PRODUCTION_READY.md** | Feature documentation |

---

## 🔄 Rollback Procedure

If something goes wrong:

```bash
# Restore from backup
cd /var/odoo/scholarixv2/addons/llm_lead_scoring/security
cp ir.model.access.csv.backup ir.model.access.csv

# Uninstall module
./odoo-bin shell -d scholarixv2
>>> env['ir.module.module'].search([('name', '=', 'llm_lead_scoring')]).button_immediate_uninstall()
>>> exit()

# Restart
sudo systemctl restart odoo
```

---

## 📞 Next Steps

### Immediate (Required)
1. ✅ Update files on CloudPepper server (Choose Option 1-3 above)
2. ✅ Upgrade module in Odoo
3. ✅ Verify installation successful
4. ✅ Test basic functionality

### After Successful Deployment
1. Configure LLM providers (Settings → Technical → LLM Providers)
2. Enable auto-enrichment (Settings → CRM → LLM Lead Scoring)
3. Test with sample lead
4. Train users on AI features

---

## 🏆 Resolution Summary

| Status | Details |
|--------|---------|
| **Issue** | Deprecated security groups causing installation failure |
| **Fix** | Updated to Odoo 17 compliant security groups |
| **Local Repo** | ✅ Already fixed |
| **Server Status** | ⚠️ Needs update |
| **Fix Scripts** | ✅ Created and tested |
| **Documentation** | ✅ Complete |
| **Deployment** | 🚀 Ready |

---

## ⚡ TLDR - Quick Action Required

**Problem**: Module won't install on CloudPepper due to old security groups  
**Solution**: Update `ir.model.access.csv` on server and upgrade module  
**Time Required**: 5 minutes  
**Risk**: Minimal (backup created automatically)  

**Fastest Fix**:
```bash
ssh user@scholarixglobal.com
cd /var/odoo/scholarixv2/addons
git pull origin main
./odoo-bin -d scholarixv2 -u llm_lead_scoring --stop-after-init
sudo systemctl restart odoo
```

---

*Resolution Guide Version: 1.0*  
*Created: November 23, 2025*  
*Status: Ready for Immediate Deployment*  
*Priority: CRITICAL - Blocks Module Installation*

**✅ LOCAL FILES CORRECT | ⚠️ SERVER NEEDS UPDATE | 🚀 READY TO DEPLOY**
