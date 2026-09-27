import re
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..lib.contract import SLUG_RE
from .sale_order import CYCLE_MONTHS, INCLUDED_USERS, PARAM_PREFIX, QUOTATION_VALID_DAYS

_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^[0-9 +()-]{6,24}$")
_COUNTRY = re.compile(r"^[A-Za-z]{2}$")

REQUIRED_KEYS = {"request_id", "slug", "company_name", "contact_name", "email", "cycle", "users"}
OPTIONAL_KEYS = {"mobile", "trade_licence_no", "country_code", "emirate", "return_url"}
# UAE emirate codes (res.country.state). The UAE VAT fiscal positions are keyed by emirate, so a
# UAE customer without one falls through to the export (0%) position. SGC is in Dubai.
EMIRATES = ("DU", "AZ", "SH", "AJ", "UQ", "RK", "FU")
DEFAULT_EMIRATE = "DU"
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS
MAX_USERS = 100
DEFAULT_RESERVED = (
    "app,www,mail,admin,api,demo,stage,staging,n8n,test,dev,billing,status,support,help,"
    "docs,portal,checkout,pay,secure,login,auth,sso,static,cdn,assets,blog,shop,osus,"
    "l3hooks,template,archive,backup,root,system,mailer,smtp,ftp,vpn"
)


class Layer3Checkout(models.TransientModel):
    """Business methods the sgctech.ai signup pages call over JSON-2 (server-side key).

    Validates the request, finds-or-creates the customer by tenant subdomain, creates the
    Order Form quotation (idempotent on request_id) and returns the hosted Sign & Pay link.
    Never creates invoices or payments itself.
    """

    _name = "layer3.checkout"
    _description = "Layer 3 signup checkout"

    @api.model
    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _flag(self, key):
        return str(self._param(key, "False")).strip().lower() in ("true", "1", "yes")

    @api.model
    def _company(self):
        raw = self._param("company_id")
        if raw:
            try:
                company = self.env["res.company"].sudo().browse(int(raw)).exists()
            except (TypeError, ValueError):
                company = None
            if company:
                return company
        return self.env.ref("base.main_company")

    # ------------------------------------------------------------- subdomains

    @api.model
    def _reserved(self):
        raw = self._param("reserved_slugs") or DEFAULT_RESERVED
        return {s.strip().lower() for s in raw.split(",") if s.strip()}

    @api.model
    def _slug_problem(self, slug, email=None):
        """None when the subdomain can be used by `email`, else a machine-readable reason."""
        if not SLUG_RE.match(slug or ""):
            return "invalid"
        if "--" in slug or slug in self._reserved():
            return "reserved"
        partner = self.env["res.partner"].sudo().search([("l3_tenant_slug", "=", slug)], limit=1)
        if partner and (not email or (partner.email or "").lower() != email.lower()):
            return "taken"
        live = self.env["sale.order"].sudo().search_count(
            [("l3_tenant_slug", "=", slug), ("state", "=", "sale")]
        )
        if live:
            return "taken"
        return None

    @api.model
    def slug_status(self, slug=None):
        slug = (slug or "").strip().lower()
        problem = self._slug_problem(slug)
        return {"slug": slug, "available": problem is None, "reason": problem or ""}

    # --------------------------------------------------------------- capacity

    @api.model
    def _capacity(self):
        cap = int(self._param("max_active_tenants", 10) or 10)
        cohort = int(self._param("founding_cohort_size", 10) or 10)
        activated = self.env["sale.order"].sudo().search_count(
            [("l3_activated_on", "!=", False), ("l3_state", "not in", ("archive", "deleted"))]
        )
        ever = self.env["sale.order"].sudo().search_count([("l3_activated_on", "!=", False)])
        return {"open": activated < cap, "founding": ever < cohort}

    # -------------------------------------------------------------- validation

    @api.model
    def _validate(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_("The request body must be a JSON object."))
        unknown = sorted(set(payload) - ALLOWED_KEYS)
        if unknown:
            raise ValidationError(_("Unsupported request keys: %s") % ", ".join(unknown))
        missing = sorted(
            k for k in REQUIRED_KEYS if payload.get(k) is None or str(payload.get(k)).strip() == ""
        )
        if missing:
            raise ValidationError(_("Missing required request keys: %s") % ", ".join(missing))

        data = {}
        data["request_id"] = str(payload["request_id"]).strip()
        if not _REQUEST_ID.match(data["request_id"]):
            raise ValidationError(_("request_id has an invalid format."))
        data["slug"] = str(payload["slug"]).strip().lower()
        data["company_name"] = str(payload["company_name"]).strip()
        if not 2 <= len(data["company_name"]) <= 120:
            raise ValidationError(_("company_name must be 2 to 120 characters."))
        data["contact_name"] = str(payload["contact_name"]).strip()
        if not 2 <= len(data["contact_name"]) <= 80:
            raise ValidationError(_("contact_name must be 2 to 80 characters."))
        data["email"] = str(payload["email"]).strip().lower()
        if not _EMAIL.match(data["email"]):
            raise ValidationError(_("email has an invalid format."))
        data["cycle"] = str(payload["cycle"]).strip().lower()
        if data["cycle"] not in CYCLE_MONTHS:
            raise ValidationError(_("cycle must be one of quarterly, half_yearly, annual."))
        try:
            data["users"] = int(str(payload["users"]).strip())
        except (TypeError, ValueError):
            raise ValidationError(_("users must be a whole number."))
        if not INCLUDED_USERS <= data["users"] <= MAX_USERS:
            raise ValidationError(_("users must be between %(a)s and %(b)s.") % {"a": INCLUDED_USERS, "b": MAX_USERS})
        data["mobile"] = str(payload.get("mobile") or "").strip()
        if data["mobile"] and not _PHONE.match(data["mobile"]):
            raise ValidationError(_("mobile has an invalid format."))
        data["trade_licence_no"] = str(payload.get("trade_licence_no") or "").strip()[:64]
        data["country_code"] = str(payload.get("country_code") or "AE").strip().upper()
        if not _COUNTRY.match(data["country_code"]):
            raise ValidationError(_("country_code must be a 2-letter ISO code."))
        data["emirate"] = False
        if data["country_code"] == "AE":
            data["emirate"] = str(payload.get("emirate") or DEFAULT_EMIRATE).strip().upper()
            if data["emirate"] not in EMIRATES:
                raise ValidationError(_("emirate must be one of %s.") % ", ".join(EMIRATES))
        return data

    # ------------------------------------------------------------------ public

    @api.model
    def create_or_get_checkout(self, payload=None, **kwargs):
        """Atomic, idempotent entry point. Returns a JSON-serialisable dict."""
        raw = dict(payload or {})
        raw.update({k: v for k, v in kwargs.items() if k not in raw})
        data = self._validate(raw)
        if not self._flag("checkout_enabled"):
            raise UserError(_("layer3_checkout_disabled"))

        company = self._company()
        self = self.with_company(company)
        Order = self.env["sale.order"].sudo()
        existing = Order.search([("l3_request_id", "=", data["request_id"])], limit=1)
        if existing:
            return self._result(existing, deduplicated=True)

        problem = self._slug_problem(data["slug"], data["email"])
        if problem:
            raise UserError(_("layer3_slug_%s") % problem)
        # The same person retrying with a new request id resumes their open quotation.
        resumable = Order.search(
            [
                ("l3_tenant_slug", "=", data["slug"]),
                ("state", "in", ("draft", "sent")),
                ("partner_id.email", "=ilike", data["email"]),
            ],
            limit=1,
        )
        if resumable:
            return self._result(resumable, deduplicated=True)

        capacity = self._capacity()
        if not capacity["open"]:
            raise UserError(_("layer3_waitlist"))
        if not capacity["founding"]:
            # The onboarding fee (OIC item 3) is one-time and sttl_sale_subscription cannot
            # mix one-time and recurring lines on one order: after the founding cohort,
            # signups are sales-assisted until that is solved.
            raise UserError(_("layer3_sales_assisted"))

        partner = self._find_or_create_partner(data, company)
        order = self._create_order(data, partner, company, founding=True)
        return self._result(order, deduplicated=False)

    @api.model
    def pricing(self):
        """Prices for the public pricing page, computed exactly as the order lines are, so the
        page and the invoice can never disagree. Amounts exclude VAT."""
        company = self._company()
        SO = self.env["sale.order"].sudo()
        capacity = self._capacity()
        base_monthly = SO._l3_float("base_monthly", 875)
        user_key = "user_monthly_founding" if capacity["founding"] else "user_monthly_standard"
        user_monthly = SO._l3_float(user_key, 50 if capacity["founding"] else 75)
        base_product = SO._l3_products()["base"]
        tax = base_product.sudo().taxes_id.filtered(lambda t: t.company_id == company)[:1]
        cycles = []
        for cycle, months in CYCLE_MONTHS.items():
            cycles.append(
                {
                    "cycle": cycle,
                    "months": months,
                    "rebate_percent": SO._l3_float("rebate_%s" % cycle, 0),
                    "base_price": SO._l3_cycle_price(cycle, base_monthly),
                    "extra_user_price": SO._l3_cycle_price(cycle, user_monthly),
                }
            )
        return {
            "currency": company.currency_id.name,
            "vat_percent": tax.amount if tax else 5.0,
            "base_monthly": base_monthly,
            "user_monthly": user_monthly,
            "included_users": INCLUDED_USERS,
            "max_users": MAX_USERS,
            "founding": capacity["founding"],
            "open": capacity["open"],
            "checkout_enabled": self._flag("checkout_enabled"),
            "cycles": cycles,
        }

    @api.model
    def order_status(self, request_id=None):
        """For the thank-you page: where is this signup now?"""
        order = self.env["sale.order"].sudo().search([("l3_request_id", "=", request_id or "")], limit=1)
        if not order:
            return {"found": False}
        return {
            "found": True,
            "order_state": order.state,
            "account_state": order.l3_state or "awaiting_payment",
            "paid": bool(order.l3_activated_on),
            "tenant_url": order.l3_tenant_url,
            "docs_status": order.l3_docs_status,
        }

    # --------------------------------------------------------------- internals

    @api.model
    def _find_or_create_partner(self, data, company):
        Partner = self.env["res.partner"].sudo()
        country = self.env["res.country"].sudo().search([("code", "=", data["country_code"])], limit=1)
        state = self.env["res.country.state"]
        if data.get("emirate") and country:
            state = state.sudo().search([("country_id", "=", country.id), ("code", "=", data["emirate"])], limit=1)
        partner = Partner.search([("l3_tenant_slug", "=", data["slug"])], limit=1)
        if partner:
            if state and not partner.state_id and partner.country_id == country:
                partner.state_id = state
            return partner
        partner = Partner.create(
            {
                "name": data["company_name"],
                "is_company": True,
                "company_type": "company",
                "email": data["email"],
                "phone": data["mobile"] or False,
                "country_id": country.id or False,
                "state_id": state.id or False,
                "l3_tenant_slug": data["slug"],
            }
        )
        Partner.create(
            {
                "name": data["contact_name"],
                "parent_id": partner.id,
                "type": "contact",
                "email": data["email"],
                "phone": data["mobile"] or False,
            }
        )
        return partner

    @api.model
    def _create_order(self, data, partner, company, founding):
        Order = self.env["sale.order"]
        products = Order._l3_products()
        period = Order._l3_period(data["cycle"])
        cycle_label = dict(self.env["sale.order"]._fields["l3_cycle"].selection)[data["cycle"]]
        lines = [
            (0, 0, {
                "product_id": products["base"].id,
                "product_uom_qty": 1,
                "name": _("SGC Real Estate Operating System - Layer 3 subscription, %(n)s users included (%(c)s billing)")
                % {"n": INCLUDED_USERS, "c": cycle_label},
            })
        ]
        extra = data["users"] - INCLUDED_USERS
        if extra:
            product = products["user_founding"] if founding else products["user_standard"]
            lines.append((0, 0, {
                "product_id": product.id,
                "product_uom_qty": extra,
                "name": _("Additional user above %(n)s (%(c)s billing)") % {"n": INCLUDED_USERS, "c": cycle_label},
            }))
        today = fields.Date.context_today(self)
        order = Order.sudo().create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "recurrance_id": period.id,
                "require_signature": True,
                "require_payment": True,
                "prepayment_percent": 1.0,
                "validity_date": today + timedelta(days=QUOTATION_VALID_DAYS),
                "client_order_ref": "Layer 3 %s" % data["slug"],
                "l3_request_id": data["request_id"],
                "l3_tenant_slug": data["slug"],
                "l3_cycle": data["cycle"],
                "l3_users": data["users"],
                "l3_founding": founding,
                "l3_admin_name": data["contact_name"],
                "l3_admin_email": data["email"],
                "l3_mobile": data["mobile"] or False,
                "l3_trade_licence_no": data["trade_licence_no"] or False,
                "l3_state": "awaiting_payment",
                "l3_docs_status": "pending",
                "note": self._order_form_terms(founding),
                "order_line": lines,
            }
        )
        if any(line.price_unit <= 0 for line in order.order_line):
            raise UserError(_("layer3_price_missing"))
        order.action_quotation_sent()
        return order

    @api.model
    def _order_form_terms(self, founding):
        """Order Form SGC-OF-2026-01 section B defaults (SGC-MEMO-2026-OIC-01)."""
        terms_url = (self._param("terms_url") or "https://sgctech.ai/legal/subscription").strip()
        rows = [
            _("Order Form SGC-OF-2026-01, issued under SGC-MEMO-2026-PR-03 (Rent - Subscription Layer)."),
            _("This order incorporates the Master Services Agreement SGC-MSA-2026-02, the Service Level Agreement SGC-SLA-2026-02 and the Data Processing Agreement SGC-DPA-2026-01, available at %s.") % terms_url,
            _("Subscription: no fixed end date; continues until cancelled with 60 days' notice, effective at the end of a billing cycle."),
            _("Additional users: AED 50 per user per month (founding rate), AED 75 (standard rate)."),
            _("One-time onboarding fee: AED 1,500 - waived (founding cohort).") if founding else _("One-time onboarding fee: AED 1,500."),
            _("Data migration: up to 1,000 records included."),
            _("Included usage: 500 AML screening queries per month, 5 GB document storage, 10,000 API calls per month; overage is agreed with the client, never billed silently."),
            _("Service levels: Standard tier (99.5% monthly uptime, support Sunday to Thursday 09:00-18:00 GST)."),
            _("Account states: Active; Grace (days 1-7 after an unpaid due date); Read-only (days 8-29); Archive (day 30 onwards)."),
            _("E-invoicing activation: not included."),
            _("All amounts are in AED and exclusive of 5% VAT."),
        ]
        return Markup("<p>%s</p>") % Markup("</p><p>").join(rows)

    @api.model
    def _base_url(self):
        base = (self._param("public_base_url") or "").strip().rstrip("/")
        return base or self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")

    def _result(self, order, deduplicated):
        return {
            "ok": True,
            "deduplicated": bool(deduplicated),
            "checkout_url": self._base_url() + order.get_portal_url(),
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "amount_total": order.amount_total,
            "currency": order.currency_id.name,
            "cycle": order.l3_cycle,
            "users": order.l3_users,
            "founding": order.l3_founding,
            "tenant_slug": order.l3_tenant_slug,
            "sale_order_name": order.name,
            "sale_order_state": order.state,
        }
