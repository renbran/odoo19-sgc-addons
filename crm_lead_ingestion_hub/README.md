# CRM Lead Ingestion Hub

Odoo 19 addon: secure webhook ingestion of leads from Meta, Google Ads,
LinkedIn, TikTok, Snapchat and any custom source, directly into native
`crm.lead`. Idempotent (dedup on redelivery), signature-verified, retried via
native `ir.cron` (no `queue_job` dependency).

## Setup

1. Install the module.
2. Go to **CRM > Lead Ingestion > Sources**, create a source config:
   - Pick the **Provider**.
   - Note the generated **Webhook Token** — the endpoint URL is:
     `https://<your-host>/crm_lead_ingestion/webhook/<provider>/<token>`
   - Set the **App Secret** (and **Verify Token** for Meta/LinkedIn) to
     match what you configure on the ad platform side.
   - Optionally set a default **Sales Team** / **Salesperson**.
3. Register the webhook URL with the ad platform:

| Provider | Where to configure | Secret needed |
|---|---|---|
| Meta | Meta App Dashboard > Webhooks > Page/Leadgen subscription | App Secret (HMAC), Verify Token (GET handshake) |
| Google Ads | Lead form extension > Webhook delivery in Google Ads UI | Shared secret sent as header/query param |
| LinkedIn | Marketing Developer Platform > Lead Sync webhook | App Secret or shared secret |
| TikTok | TikTok for Business > Lead Generation > Webhook | App Secret (HMAC) |
| Snapchat | Snapchat Ads Manager > Lead Generation webhook | App Secret (HMAC) |
| Universal | Any custom system (website form, Zapier, Make) | Shared secret you choose |

4. For Meta/LinkedIn, the platform will send a GET verification request —
   this module answers it automatically as long as the Verify Token matches.

## Field mapping

Each provider adapter maps common fields (name, email, phone, company) to
`crm.lead` by default. Add rows under the source config's **Field Mapping**
tab to map any additional payload key (dot-path, e.g. `user_column_data.EMAIL`)
to any `crm.lead` field.

## Test mode

Enable **Test Mode** on a source config to log inbound webhooks without
creating real CRM leads — use this while validating a new webhook
registration.

## Troubleshooting

Check **CRM > Lead Ingestion > Ingestion Logs**. Each row shows the raw and
parsed payload, status, and (for `failed`/`rejected`) the error message.
- `rejected` — signature verification failed; check the App Secret matches.
- `failed` — payload parsed but lead creation errored; the retry cron
  (runs every 10 minutes) will retry automatically up to Max Retries.
- `duplicate` — the same lead was already ingested (expected on provider
  redelivery).

Logs older than a source config's **Retention Days** are purged daily.
