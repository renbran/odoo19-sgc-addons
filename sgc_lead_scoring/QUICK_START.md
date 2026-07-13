# LLM Lead Scoring - Quick Start Guide

## 5-Minute Setup

### Step 1: Install the Module (1 minute)

1. Install the module from Odoo Apps
2. The module will be ready with default (inactive) provider configurations

### Step 2: Configure Your LLM Provider (2 minutes)

**Option A: Use OpenAI (Recommended for testing)**

1. Get API key from https://platform.openai.com/api-keys
2. Go to **LLM Lead Scoring > Configuration > LLM Providers**
3. Edit "OpenAI GPT-4" provider:
   - Paste your API key
   - Change model to `gpt-3.5-turbo` (cheaper for testing)
   - Check "Active"
   - Check "Default Provider"
   - Save

**Option B: Use Groq (Recommended for production - faster & cheaper)**

1. Get free API key from https://console.groq.com/keys
2. Go to **LLM Lead Scoring > Configuration > LLM Providers**
3. Edit "Groq Llama 3.1 70B" provider:
   - Paste your API key
   - Check "Active"
   - Check "Default Provider"
   - Save

### Step 3: Test on a Lead (1 minute)

1. Open any CRM Lead/Opportunity
2. Add some description text (e.g., "Looking for CRM solution for 50 users, need integration with email")
3. Click **"AI Enrich"** button in header
4. Wait 5-10 seconds
5. Check the "AI Scoring" tab - you should see scores!
6. Check internal notes for detailed enrichment report

### Step 4: Enable Auto-Enrichment (1 minute)

1. Go to **Settings > CRM Settings**
2. Scroll to "LLM Lead Scoring" section
3. Enable features you want:
   - ✅ Enable Auto-Enrichment
   - ✅ Auto-Enrich New Leads
   - ✅ Enable Customer Research
4. Save

## That's it! 🎉

Your leads will now automatically get AI scores when created or updated.

## Next Steps

- **Batch process existing leads**: Select multiple leads > Action > "AI Enrich Selected Leads"
- **Customize scoring weights**: Adjust in Settings to match your sales process
- **Review enrichment reports**: Check internal notes on enriched leads
- **Monitor API usage**: Check provider statistics in LLM Providers menu

## Common First-Time Issues

**"No LLM provider configured"**
→ Make sure you activated a provider and checked "Default Provider"

**API Error 401**
→ Double-check your API key is correct and has credits

**Very low scores on all leads**
→ Normal! Add more information to leads (description, contact details) for better scores

**Enrichment too slow**
→ Disable "Customer Research" in settings to speed up (removes 1 API call)

## Cost Estimate

- **OpenAI GPT-3.5**: ~$0.001 per lead (~$1 per 1000 leads)
- **OpenAI GPT-4**: ~$0.02 per lead (~$20 per 1000 leads)
- **Groq**: Free tier available, very low cost after

## Support

Need help? Check the full README.md for detailed documentation.
