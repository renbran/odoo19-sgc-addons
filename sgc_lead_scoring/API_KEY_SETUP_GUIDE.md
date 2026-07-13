# 🔑 LLM API Key Setup Guide

## Quick Fix for "Invalid API Key" Error

If you're seeing this error:
```
API Error 401: {"error":{"message":"Invalid API Key","type":"invalid_request_error","code":"invalid_api_key"}}
```

Follow these steps to fix it:

---

## Step 1: Choose Your LLM Provider

### Recommended Free Options:
1. **Groq** (Fastest, Free Tier) - **RECOMMENDED**
   - 🚀 Fastest inference speed
   - ✅ Generous free tier
   - 📝 Sign up: https://console.groq.com/keys
   - Models: `llama-3.1-70b-versatile`, `mixtral-8x7b-32768`

2. **OpenAI** (Most Accurate, Paid)
   - 🎯 Best quality responses
   - 💰 Requires paid account (~$0.002 per request)
   - 📝 API Keys: https://platform.openai.com/api-keys
   - Models: `gpt-4o-mini`, `gpt-4`, `gpt-3.5-turbo`

3. **Google Gemini** (Good Balance, Free Tier)
   - ⚖️ Good balance of speed and quality
   - ✅ Free tier available
   - 📝 API Keys: https://makersuite.google.com/app/apikey
   - Models: `gemini-1.5-flash`, `gemini-1.5-pro`

4. **HuggingFace** (Open Source, Free)
   - 🔓 Open source models
   - ✅ Free tier
   - 📝 Tokens: https://huggingface.co/settings/tokens
   - Models: Various open models

---

## Step 2: Get Your API Key

### For Groq (Recommended):
1. Visit: https://console.groq.com/keys
2. Sign up/Login with Google or email
3. Click "Create API Key"
4. Copy your key (starts with `gsk_...`)
5. **Save it securely** - you won't see it again!

### For OpenAI:
1. Visit: https://platform.openai.com/api-keys
2. Login to your account
3. Click "+ Create new secret key"
4. Name it (e.g., "Odoo Lead Scoring")
5. Copy your key (starts with `sk-...`)

### For Google Gemini:
1. Visit: https://makersuite.google.com/app/apikey
2. Login with Google account
3. Click "Create API key"
4. Copy your key

---

## Step 3: Configure in Odoo

### Method 1: Via Settings (Recommended)
1. Go to **CRM → Configuration → Settings**
2. Scroll to **LLM Lead Scoring** section
3. Click on **Default LLM Provider** field
4. Click **Create and Edit** or select existing provider
5. Fill in:
   - **Provider Name**: `My Groq Provider` (or your choice)
   - **Provider Type**: Select your provider
   - **API Key**: Paste your key
   - **Model Name**: 
     - Groq: `llama-3.1-70b-versatile`
     - OpenAI: `gpt-4o-mini`
     - Google: `gemini-1.5-flash`
   - **Is Default**: ✅ Check this
6. Click **Save**

### Method 2: Via LLM Providers Menu
1. Go to **CRM → Configuration → LLM Providers**
2. Click **Create**
3. Fill in the same details as above
4. Click **Save**

---

## Step 4: Test the Configuration

1. Go to **CRM → Leads**
2. Open any lead
3. Click **Enrich with AI** button
4. You should see:
   - ✅ AI Probability Scores calculated
   - ✅ Analysis provided
   - ✅ Customer Research (if enabled)

---

## Common Issues & Solutions

### ❌ "No LLM provider configured"
**Solution**: Create an LLM Provider following Step 3

### ❌ "Invalid API Key" (401 Error)
**Solutions**:
1. Double-check your API key (no extra spaces)
2. Ensure key hasn't expired
3. For OpenAI: Add credits to your account
4. Try regenerating a new key

### ❌ "Model Not Found" (404 Error)
**Solutions**:
1. Check model name spelling
2. Common valid models:
   - Groq: `llama-3.1-70b-versatile`, `mixtral-8x7b-32768`
   - OpenAI: `gpt-4o-mini`, `gpt-3.5-turbo`, `gpt-4`
   - Google: `gemini-1.5-flash`, `gemini-1.5-pro`

### ❌ "Access Forbidden" (403 Error)
**Solutions**:
1. Your API key might not have access to that model
2. For OpenAI: Upgrade your plan
3. Try a different model from the free tier

### ❌ "Rate Limit" (429 Error)
**Solutions**:
1. Wait a few seconds and try again
2. The system auto-retries with backoff
3. For heavy usage: upgrade your API plan

---

## Cost Estimates

### Groq (Free Tier):
- **Cost**: FREE
- **Limits**: 30 requests/minute, 7000 requests/day
- **Perfect for**: Testing, small teams

### OpenAI (Paid):
- **GPT-4o-mini**: ~$0.002 per lead enrichment
- **GPT-3.5-turbo**: ~$0.001 per lead enrichment
- **Monthly estimate** (100 leads): ~$0.20 - $2.00

### Google Gemini (Free Tier):
- **Cost**: FREE up to 60 requests/minute
- **Perfect for**: Medium-sized teams

---

## Recommended Configuration

For best results with minimal cost:

```
Provider Type: Groq
Model Name: llama-3.1-70b-versatile
Temperature: 0.7
Max Tokens: 2000
Timeout: 30 seconds
```

This provides:
- ✅ Fast responses (< 2 seconds)
- ✅ Good quality analysis
- ✅ FREE for most use cases
- ✅ No credit card required

---

## Security Best Practices

1. **Never share your API keys** publicly or in code
2. **Use separate keys** for different environments (dev/prod)
3. **Rotate keys regularly** (every 90 days)
4. **Monitor usage** in your provider dashboard
5. **Set spending limits** if using paid providers

---

## Need Help?

If you're still having issues:
1. Check the Odoo logs: **Settings → Technical → Logging**
2. Look for errors mentioning `llm.provider` or `llm.service`
3. Verify your API key works outside Odoo (test with cURL or Postman)
4. Contact your system administrator

---

## Testing Your Setup with cURL

### Test Groq API:
```bash
curl -X POST https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama-3.1-70b-versatile",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 100
  }'
```

### Test OpenAI API:
```bash
curl -X POST https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Say hello"}],
    "max_tokens": 100
  }'
```

If these work but Odoo doesn't, check your Odoo firewall/proxy settings.

---

**Last Updated**: November 23, 2025
**Module Version**: 17.0.1.0.0
