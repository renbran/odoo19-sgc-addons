# SGC Digital Product Delivery — Production Readiness & How-To Guide

> **Module:** `sgc_digital_delivery`  
> **Version:** 19.0.1.2.0  
> **Author:** SGC TECH AI  
> **License:** LGPL-3  

---

## 1. Production Readiness Assessment

### ✅ What's Working Well

| Area | Detail |
|------|--------|
| **Security — Token Auth** | Download URL uses Odoo's `portal.mixin` `access_token`; compared with `consteq()` (constant-time, no timing-attack risk) |
| **Security — IR Rules** | `sgc_digital_security.xml` blocks portal and public users from accessing `digital_file` attachments directly via `/web/content` |
| **Input Validation** | All three URL params (`order_id`, `access_token`, `product_id`) are validated; non-integer, non-positive, and oversized (>256 char) tokens are rejected with `403 Forbidden` |
| **Filename Sanitization** | `_sanitize_filename()` strips directory traversal (`../`) and unsafe characters before serving |
| **File Size Limit** | ORM `@api.constrains` enforces 50 MB max; friendly validation error shown to product managers |
| **Database Savepoint** | `with self.env.cr.savepoint()` wraps email send — a mail failure does not corrupt the parent transaction |
| **Thread-Safe Counter** | Download count incremented via raw SQL `UPDATE ... SET count = count + 1` — safe under concurrent requests |
| **Secure HTTP Headers** | `X-Content-Type-Options: nosniff`, `Cache-Control: no-store` set on every download response |
| **Error State Tracking** | `digital_delivery_state` field tracks `none / pending / sent / partial / error` with chatter logging |
| **Portal Token Guard** | `_portal_ensure_token()` called before building email links — prevents broken download URLs for backend orders |
| **Mail API** | Uses Odoo's standard `template.send_mail()` — retries and mail logs are handled by Odoo's mail queue |
| **Access Control** | `digital_file` field is restricted to `product.group_product_manager` group |
| **`noupdate="1"` on data** | Mail template and security rules are protected from accidental overwrites during module upgrades |

---

### ⚠️ Known Limitations / Things to Be Aware Of

| # | Issue | Impact | Recommendation |
|---|-------|--------|----------------|
| 1 | **No download link expiry** | Links are valid for the lifetime of the sale order (state `sale`/`done`). A buyer can re-download indefinitely. | Acceptable for most use cases. Add a `digital_download_limit` field if single-download enforcement is needed. |
| 2 | **File loaded entirely into memory** | `base64.b64decode(digital_file)` loads the full binary into RAM per request. At 50 MB × concurrent users, RAM usage can spike. | Acceptable at low-to-medium volume. For high traffic consider streaming via `ir.attachment` file store path. |
| 3 | **`force_send=True` on email** | Email is sent synchronously during order confirmation. A slow mail server will delay the HTTP response. | Switch to `force_send=False` to queue emails if you experience timeouts. |
| 4 | **Hardcoded contact URL in email template** | Footer links to `https://sgctech.ai/contact`. | Update the mail template from **Settings → Technical → Email Templates** after installation. |
| 5 | **No rate limiting on download endpoint** | A buyer (or attacker with a valid token) can hammer `/shop/digital/download`. | Add Nginx/Caddy rate limiting in front of Odoo for production deployments. |
| 6 | **Website template XPath fragility** | Product detail page XPath targets `t-call='website_sale.add_to_cart_snippet_form_submit'`. If Odoo renames this call in a future patch, the notice won't render. | Monitor Odoo changelogs on `website_sale.add_to_cart_snippet_form_submit` across upgrades. |
| 7 | **`ir.model.access.csv` is empty** | No rows — intentional, as no new models are introduced. The module only inherits `product.template` and `sale.order`. | No action needed. |
| 8 | **No automated tests** | No `tests/` directory present. No automated regression detection. | Add unit tests for: token validation, payment detection, filename sanitization, and download count atomicity before deploying at high scale. |

---

### 🏁 Verdict: **Production Ready**

The module follows Odoo security best practices, has correct error handling, uses standard framework APIs, and guards all attack surfaces at the controller level. The limitations above are operational considerations, not blocking issues.

---

## 2. How-To Guide

### 2.1 Prerequisites

- Odoo 19 instance with the following apps installed:
  - **Sales** (`sale_management`)
  - **eCommerce** (`website_sale`)
  - **Invoicing / Accounting** (`account`)
  - **Discuss** (`mail`)
  - **Portal** (`portal`)
- A working outgoing mail server configured in **Settings → Technical → Outgoing Mail Servers**
- User account with **Sales / Administrator** (or `product.group_product_manager`) access

---

### 2.2 Installation

#### Option A — ZIP Upload (Recommended for Production)

1. Package the module folder as a ZIP:
   ```
   sgc_digital_delivery.zip
   └── sgc_digital_delivery/
       ├── __manifest__.py
       ├── models/
       ├── controllers/
       ├── views/
       ├── data/
       ├── security/
       └── static/
   ```
2. In Odoo go to **Apps → Upload a Module** (requires developer mode).
3. Upload the ZIP and click **Install**.

#### Option B — Addons Path

1. Copy the `sgc_digital_delivery` folder to your Odoo addons directory (e.g., `/opt/odoo/custom/`).
2. Ensure the path is listed in `odoo.conf`:
   ```ini
   addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom
   ```
3. Restart Odoo:
   ```bash
   sudo systemctl restart odoo
   ```
4. In Odoo go to **Apps → Update Apps List**, then search for **"SGC Digital"** and click **Install**.

---

### 2.3 Activating Developer Mode

Most configuration steps require developer mode:

**Settings → (scroll to bottom) → Activate the developer mode**

OR append `?debug=1` to the URL.

---

### 2.4 Configuring a Digital Product

1. Navigate to **Sales → Products → Products** (or **Website → eCommerce → Products**).
2. Open (or create) a product.
3. Click the **Digital Delivery** tab.
4. Toggle **Digital Product** to ON.
5. Fill in:
   - **File Name** — the filename the buyer sees when downloading (e.g., `my-product-v2.zip`)
   - **Digital File** — click **Upload** and select your file (max 50 MB)
6. Save the product.

> 💡 Only users in the **Product Manager** security group can see and upload the digital file field.

---

### 2.5 How the Delivery Flow Works

```
Customer adds digital product to cart
          ↓
Customer checks out and pays (Stripe, PayPal, etc.)
          ↓
Odoo payment provider marks transaction as "done"
          ↓
sale.order.action_confirm() is triggered
          ↓
Module detects digital lines → sets state = "pending"
          ↓
_digital_payment_confirmed() returns True
          ↓
_send_digital_products() emails buyer:
  • Secure download link(s) per product
  • File(s) attached to the email
          ↓
state = "sent" (or "partial" if some files missing)
          ↓
Buyer clicks "Download File" in email
          ↓
Controller validates: order_id + access_token + product_id
          ↓
File is served with secure headers
          ↓
digital_download_count incremented
```

---

### 2.6 Manual Resend (Backend Orders / B2B)

For orders created in the backend (no eCommerce payment flow):

1. Open the sale order in **Sales → Orders → Orders**.
2. Confirm payment via the usual invoice/payment workflow.
3. Once payment is registered, a **"Resend Digital Files"** button appears in the order header.
4. Click it — a green success notification confirms the email was sent.

> 🔒 Only users in the **Sales Manager** group can see and use this button.

---

### 2.7 Monitoring Delivery Status

In the **sale order form**, look for the **Digital Delivery** badge next to the order status:

| Badge Color | State | Meaning |
|-------------|-------|---------|
| 🔵 Blue | Pending | Digital lines detected; email not yet sent |
| 🟢 Green | Sent | All download links emailed successfully |
| 🟡 Yellow | Partial | Some files were missing; partial email sent |
| 🔴 Red | Error | Delivery failed (check logs / partner email) |

In the **sale order list**, an optional **Digital** column shows the state at a glance.

---

### 2.8 Customising the Email Template

The default email template uses SGC's branding. To customise:

1. Go to **Settings → Technical → Email Templates** (developer mode required).
2. Search for **"Digital Product Delivery"**.
3. Edit the subject, body, or footer as needed.
4. Especially update the hardcoded contact URL in the footer:
   ```
   Questions? Contact us → change to your own URL
   ```

> ⚠️ The template has `noupdate="1"` — your edits will **not** be overwritten by module upgrades.

---

### 2.9 Checking the Download Count

1. Open the product form.
2. On the **Digital Delivery** tab, see **Times Delivered** — incremented each time a buyer clicks the download link (not when the email is sent).

---

### 2.10 Website Shop Integration

The module automatically adds visual indicators on the website:

- **Shop product card** — a `⬇ DIGITAL` badge appears above the "Add to Cart" button.
- **Product detail page** — a blue info notice reads:
  > *"Digital Product — You will receive a secure download link by email immediately after payment is confirmed."*

No configuration is required; these are activated automatically when `is_digital = True`.

---

### 2.11 Security Architecture (Reference)

```
Direct /web/content URL
        ↓
ir.rule: "deny portal/public access to digital_file attachments"
        ↓ BLOCKED for portal/public users

Secure download URL: /shop/digital/download
        ↓
1. All params present? (order_id, access_token, product_id)
2. IDs are positive integers?
3. Token length ≤ 256 chars?
4. Order exists?
5. consteq(token, order.access_token)?  ← constant-time compare
6. Order state in ('sale', 'done')?
7. product_id is a digital line on this exact order?
        ↓ ALL CHECKS PASS
File served with: Content-Disposition, X-Content-Type-Options, Cache-Control: no-store
```

---

### 2.12 Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Buyer gets no email | Partner has no email address | Add email to the contact record |
| `digital_delivery_state = error` | Email send failed | Check **Settings → Technical → Emails** for bounces; check Odoo logs |
| Download returns 403 | Expired/wrong token or order cancelled | Verify order is in `sale`/`done` state; use Resend button |
| Download returns 404 | File not attached or product not on order | Re-upload digital file on product; verify product is on the order |
| "File exceeds 50 MB" on upload | File too large | Compress file or use external hosting and share a URL in the product description |
| Badge not showing on website | Theme XPath conflict | Check website_shop_templates.xml XPath; inspect page HTML for conflicts |
| Mail template missing | Data record not loaded | Re-upgrade module: `./odoo-bin -u sgc_digital_delivery` |

---

### 2.13 Upgrading the Module

```bash
# Stop Odoo, upgrade the module, restart
./odoo-bin -u sgc_digital_delivery -d <your_db>
```

- Mail template and security rules (`noupdate="1"`) are **not** re-applied — manual edits are preserved.
- New model fields are added automatically by the ORM.

---

### 2.14 Pre-Production Checklist

Before going live, verify these items:

- [ ] Outgoing mail server configured and tested
- [ ] Test with your active payment provider (Stripe, PayPal, Mollie, etc.)
- [ ] Test ecommerce checkout → instant download email received
- [ ] Test backend (B2B) order → "Resend Digital Files" button works
- [ ] Customise email template footer (remove hardcoded `sgctech.ai/contact`)
- [ ] Verify portal token generated for backend orders (check email download links work)
- [ ] Test order cancellation — confirm download link returns 403
- [ ] Test with `.zip`, `.pdf`, and any other file types you'll sell
- [ ] Test malformed/special character filenames
- [ ] Check email renders correctly in Gmail and Outlook
- [ ] Set up Nginx/Caddy rate limiting on `/shop/digital/download`
- [ ] Brief support team on: resend procedure, missing token troubleshooting, 50 MB limit

---

## 3. Quick Reference

### URL Structure of Download Link

```
https://<your-domain>/shop/digital/download
  ?order_id=<sale.order id>
  &access_token=<portal access token>
  &product_id=<product.product id>
```

### Key Fields Added

| Model | Field | Type | Purpose |
|-------|-------|------|---------|
| `product.template` | `is_digital` | Boolean | Marks product as digital |
| `product.template` | `digital_file` | Binary (attachment) | Stores the downloadable file |
| `product.template` | `digital_filename` | Char | Filename shown to buyer |
| `product.template` | `digital_download_count` | Integer | Times file was downloaded |
| `product.product` | `is_digital` | Boolean (related) | Exposes flag on variant level |
| `sale.order` | `digital_delivery_state` | Selection | Tracks delivery state |
| `sale.order` | `digital_delivery_date` | Datetime | When email was sent |

### Security Groups Required

| Action | Required Group |
|--------|---------------|
| Upload digital file | `product.group_product_manager` |
| Resend digital files | `sales_team.group_sale_manager` |
| View delivery state | Any internal user |

---

*Document generated: 2026-03-20 | SGC TECH AI | https://sgctech.ai*
