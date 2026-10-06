# CRM AI Field Compatibility Module

## 🚨 Emergency Fix for Production

### Problem
Production error: `"crm.lead"."ai_enrichment_report" field is undefined` causing OwlError and preventing CRM lead forms from loading.

### Solution
This module provides an emergency compatibility layer that ensures the `ai_enrichment_report` field exists on `crm.lead` model, preventing the OwlError crash.

### Installation Priority
**CRITICAL** - Install immediately to restore CRM functionality

### Installation Steps

#### CloudPepper Deployment:
```bash
# 1. Upload module to CloudPepper
scp -r crm_ai_field_compatibility/ user@scholarixglobal.com:/opt/odoo/addons/

# 2. SSH to server
ssh user@scholarixglobal.com

# 3. Install module
odoo -u crm_ai_field_compatibility --stop-after-init

# 4. Restart Odoo
sudo systemctl restart odoo
```

#### Local Testing:
```bash
# Restart Odoo and install
./odoo-bin -u crm_ai_field_compatibility --stop-after-init
```

### What This Module Does
1. ✅ Adds `ai_enrichment_report` field to `crm.lead` if missing
2. ✅ Provides compatibility compute method to prevent conflicts
3. ✅ Uses non-stored field to avoid database conflicts
4. ✅ Gracefully coexists with `llm_lead_scoring` module
5. ✅ Prevents OwlError on production

### When to Use
- **Immediate**: When `llm_lead_scoring` module is not installed but views reference AI fields
- **Temporary**: Until `llm_lead_scoring` is properly installed and upgraded
- **Permanent**: As a safety layer for mixed-module environments

### Next Steps After Installation
1. Verify CRM lead forms load without error
2. Test lead creation and editing
3. Plan `llm_lead_scoring` module installation/upgrade
4. Monitor logs for any field conflicts

### Compatibility
- **Odoo Version**: 17.0
- **Dependencies**: `crm` (base)
- **Conflicts**: None - designed to coexist with `llm_lead_scoring`

### Module Behavior
- If `llm_lead_scoring` is NOT installed: Provides placeholder field
- If `llm_lead_scoring` IS installed: Defers to that module's field definition

### Troubleshooting
If error persists after installation:
1. Clear browser cache (Ctrl+Shift+R)
2. Clear Odoo asset cache: `rm -rf /opt/odoo/.local/share/Odoo/filestore/*/assets/*`
3. Regenerate assets: `odoo --update=web --stop-after-init`
4. Restart Odoo service
5. Check logs: `tail -f /var/log/odoo/odoo.log | grep ai_enrichment`

### Author
OSUS Properties - Emergency Response Team

### License
LGPL-3
