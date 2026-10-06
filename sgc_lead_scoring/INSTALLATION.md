# LLM Lead Scoring - Installation Guide

## Prerequisites

- Odoo 17.0 or later
- Python 3.8+
- `requests` library (included in standard Odoo installation)
- Active API key from at least one LLM provider

## Installation Steps

### 1. Add Module to Odoo

**Option A: Copy to addons directory**
```bash
cp -r llm_lead_scoring /path/to/odoo/addons/
```

**Option B: Add custom addons path**
```bash
# In odoo.conf
addons_path = /path/to/odoo/addons,/path/to/custom/addons
```

### 2. Update Apps List

1. Restart Odoo server
2. Go to **Apps** menu
3. Click **Update Apps List**
4. Search for "LLM Lead Scoring"

### 3. Install Module

1. Find "LLM Lead Scoring" in Apps list
2. Click **Install**
3. Wait for installation to complete

### 4. Configure LLM Provider

After installation, you need to configure at least one LLM provider:

#### Option 1: OpenAI

1. Get API key from https://platform.openai.com/api-keys
2. Go to **LLM Lead Scoring > Configuration > LLM Providers**
3. Edit "OpenAI GPT-4" or create new provider:
   ```
   Name: OpenAI GPT-3.5
   Provider Type: OpenAI
   Model Name: gpt-3.5-turbo
   API Key: sk-your-api-key-here
   Temperature: 0.7
   Max Tokens: 2000
   Active: ✓
   Default Provider: ✓
   ```
4. Save

#### Option 2: Groq (Recommended - Fast & Free Tier)

1. Get free API key from https://console.groq.com/keys
2. Go to **LLM Lead Scoring > Configuration > LLM Providers**
3. Edit "Groq Llama 3.1 70B":
   ```
   API Key: gsk_your-groq-api-key-here
   Active: ✓
   Default Provider: ✓
   ```
4. Save

#### Option 3: Anthropic Claude

1. Get API key from https://console.anthropic.com/
2. Create new provider:
   ```
   Name: Claude 3 Sonnet
   Provider Type: Anthropic (Claude)
   Model Name: claude-3-sonnet-20240229
   API Key: sk-ant-your-api-key-here
   Temperature: 0.7
   Max Tokens: 2000
   Active: ✓
   Default Provider: ✓
   ```

### 5. Configure Module Settings

1. Go to **Settings > CRM Settings**
2. Scroll to "LLM Lead Scoring" section
3. Configure options:
   - ✓ Enable Auto-Enrichment (for scheduled job)
   - ✓ Auto-Enrich New Leads (optional)
   - ✓ Auto-Enrich on Update (optional)
   - ✓ Enable Customer Research
   - Select Default LLM Provider
   - Adjust scoring weights if needed (default: 30/40/30)
4. Save

### 6. Test the Module

1. Go to **CRM > Leads** or **CRM > Pipeline**
2. Open any lead/opportunity
3. Add description: "Looking for CRM solution for 50 users"
4. Click **"AI Enrich"** button
5. Wait 5-15 seconds
6. Check results:
   - "AI Scoring" tab shows scores
   - Internal notes show enrichment report
   - AI probability score visible on form

### 7. Enable Scheduled Job (Optional)

To enable automatic background enrichment:

1. Go to **Settings > Technical > Automation > Scheduled Actions**
2. Search for "LLM Lead Scoring: Auto Enrich Leads"
3. Edit the record:
   - Active: ✓
   - Interval: 1 Hour (or adjust as needed)
4. Save

Now leads with "Auto Enrich" enabled will be processed automatically.

## Post-Installation Configuration

### Customize Scoring Weights

In Settings > CRM Settings > LLM Lead Scoring:
- **Completeness Weight**: How much lead information completeness matters (default: 30%)
- **Clarity Weight**: How much requirement clarity matters (default: 40%)
- **Engagement Weight**: How much activity/engagement matters (default: 30%)

Must total 100%.

### Configure Multiple Providers

You can configure multiple providers for:
- **Redundancy**: Fallback if one provider is down
- **Cost optimization**: Use cheaper providers for initial scoring
- **Performance testing**: Compare different models

### Batch Process Existing Leads

To enrich all existing leads:

1. Go to **CRM > Leads** (list view)
2. Remove all filters to see all leads
3. Select leads to enrich (up to 50-100 at a time)
4. **Action** > **AI Enrich Selected Leads**
5. Click **Enrich Leads**

**Note**: For large volumes (1000+ leads), process in batches to avoid timeout.

## Verification

### Test Checklist

- [ ] Module installed successfully
- [ ] At least one LLM provider configured and active
- [ ] Default provider selected in settings
- [ ] Manual enrichment works on a test lead
- [ ] AI scores visible in lead form
- [ ] Enrichment report appears in internal notes
- [ ] Batch enrichment wizard accessible
- [ ] Settings page shows LLM Lead Scoring section

### Check Logs

If issues occur, check Odoo logs:
```bash
tail -f /var/log/odoo/odoo.log | grep -i "llm"
```

Look for:
- ✓ "Calling LLM API: [Provider Name]"
- ✓ "Successfully enriched lead [Name] with AI score: [Score]"
- ✗ "LLM API Error: [Error details]"

## Troubleshooting Installation Issues

### Module Not Appearing in Apps List

1. Check module is in correct addons directory
2. Verify `__manifest__.py` has no syntax errors
3. Restart Odoo server
4. Update Apps List again

### Installation Fails

**Check dependencies:**
```bash
pip install requests
```

**Check Odoo logs for errors:**
```bash
tail -100 /var/log/odoo/odoo.log
```

### "Module not found" Error

Ensure addons path includes the module directory:
```bash
# In odoo.conf
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/path/to/llm_lead_scoring
```

### Database Update Required

If prompted, run database update:
```bash
odoo-bin -d your_database -u llm_lead_scoring
```

## Upgrading

### From Previous Version

1. Backup your database
2. Copy new module files
3. Restart Odoo
4. Go to Apps > LLM Lead Scoring > Upgrade
5. Test functionality

## Uninstallation

To remove the module:

1. Go to **Apps**
2. Search "LLM Lead Scoring"
3. Click **Uninstall**
4. Confirm

**Warning**: This will remove all AI scores and enrichment data from leads.

## Next Steps

- Read [QUICK_START.md](QUICK_START.md) for 5-minute setup
- Read [README.md](README.md) for full documentation
- Configure auto-enrichment based on your workflow
- Train your team on using AI scores

## Support

If you encounter issues:
1. Check troubleshooting section above
2. Review Odoo logs
3. Verify API key and credits
4. Contact support with logs and error details

---

**Happy Scoring! 🎯**
