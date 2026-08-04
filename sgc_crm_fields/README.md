# sgc-crm-fields — Odoo module skeleton (reference)

Custom fields on `crm.lead` required by the signature pipeline write-back.
The field list is authoritative in `10-signature/odoo-mapping.yaml`; keep this
module in sync with it.

## Status

**Reference skeleton — not installed anywhere.** This repository contains
proposal-engine documentation and validation only. The module must be ported
into the `odoo19-sgc` repository (or the client's Odoo instance) by an Odoo
developer before go-live.

## Porting checklist

1. Copy `sgc-crm-fields/` into the target Odoo addons directory (odoo19-sgc).
2. Adjust `__manifest__.py` — `version` (match target Odoo), `depends`
   (`base`, `crm`, `account`), `license`, author if different.
3. Confirm the target Odoo version supports these field types on `crm.lead`
   (Char/Datetime/Integer/Float/Selection/Text/Date/Many2one — standard).
4. Install the module (Apps → Update Apps List → Install `sgc_crm_fields`).
5. Verify fields appear on the opportunity form (Developer mode → they are
   on the lead model; add to form views as desired by the SDR team).
6. The webhook handler writes these fields via Odoo External API
   (JSON-RPC 2.0, `Bearer <api_key>`); the External API key is created in
   Odoo under the user's Preferences → Account Security → API Keys, and must
   be provisioned to `ODOO_API_KEY` on the handler service.

## Fields (17 + 1 relation)

| Field | Type | Purpose |
|---|---|---|
| x_envelope_id | Char | Zoho Sign envelope ID |
| x_signed_pdf_hash | Char | SHA-256 of signed PDF |
| x_frozen_pdf_hash | Char | SHA-256 of frozen sent PDF |
| x_sent_date | Datetime | Envelope sent at |
| x_completed_date | Datetime | Fully executed at |
| x_signing_actor_client | Char | Client signatory |
| x_signing_actor_sgc | Char | SGC signatory |
| x_decline_reason | Text | Decline reason |
| x_contract_term_months | Integer | Initial term |
| x_subscription_fee | Float | Monthly total (AED) |
| x_platform_fee | Float | Platform portion (AED) |
| x_recovery_fee | Float | Recovery portion (AED) |
| x_mobilisation_amount | Float | One-off mobilisation (AED) |
| x_cadence | Selection | quarterly/monthly/annual in advance |
| x_edition | Selection | community / enterprise |
| x_upgrade_policy | Text | Upgrade policy text |
| x_kickoff_date | Date | Target kickoff |
| x_invoice_id | Many2one account.move | Draft mobilisation invoice (G51) |

Never store credentials in this module. The webhook handler keeps all secrets
in environment variables (G52).
