import logging
import re

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Commercial contract (must stay in step with KartaTap's src/lib/tier.ts).
PLANS = ("SOLO", "TEAM", "BUSINESS")
MIN_SEATS = {"SOLO": 1, "TEAM": 2, "BUSINESS": 2}
PRODUCT_CODE_PARAM = {
    "SOLO": "product_code_solo",
    "TEAM": "product_code_team",
    "BUSINESS": "product_code_business",
}
DEFAULT_PRODUCT_CODE = {
    "SOLO": "KT-SOLO",
    "TEAM": "KT-TEAM",
    "BUSINESS": "KT-BUSINESS",
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[A-Za-z]{2,}$")
_COUNTRY = re.compile(r"^[A-Za-z]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")

# KartaTap's billing intervals -> product.subscription.period.unit (duration 1).
BILLING_INTERVALS = ("month", "year")

REQUIRED_KEYS = {
    "kartatap_company_id",
    "kartatap_request_id",
    "plan_code",
    "quantity",
    "currency",
    "company_name",
}
OPTIONAL_KEYS = {"admin_email", "country_code", "return_url", "cancel_url", "billing_interval"}
ALLOWED_KEYS = REQUIRED_KEYS | OPTIONAL_KEYS

MAX_QUANTITY = 100
MAX_URL_LENGTH = 300
KARTATAP_HOST_SUFFIX = ".kartatap.com"

PARAM_PREFIX = "sgc_kartatap_bridge."


class KartatapCheckout(models.TransientModel):
    """The single atomic business method KartaTap calls to start a hosted checkout.

    It validates the request, resolves the tenant partner by its immutable KartaTap
    identifier, finds-or-creates the quotation (idempotent on the request id), attaches
    the recurring plan and returns the hosted payment link.

    It never creates invoices, payments or accounting entries, and it never calls out to
    KartaTap. Everything it writes is scoped to the KartaTap company resolved by
    `_resolve_company()`.
    """

    _name = "kartatap.checkout"
    _description = "KartaTap hosted checkout (atomic Odoo-side business method)"

    # ------------------------------------------------------------------ config

    @api.model
    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _resolve_company(self):
        raw = self._param("company_id")
        if raw:
            try:
                company = self.env["res.company"].sudo().browse(int(raw)).exists()
            except (TypeError, ValueError):
                company = self.env["res.company"]
            if company:
                return company
        company = self.env["res.company"].sudo().search([("name", "=", "KartaTap")], limit=1)
        if not company:
            raise UserError(
                _("The KartaTap company is not configured. Set the system parameter %scompany_id.")
                % PARAM_PREFIX
            )
        return company

    @api.model
    def _period_for(self, interval):
        period = self.env["product.subscription.period"].sudo().search(
            [("unit", "=", interval), ("duration", "=", 1)], order="id", limit=1
        )
        if not period:
            raise UserError(
                _("No 1-%(unit)s subscription period is configured in Odoo.") % {"unit": interval}
            )
        return period

    @api.model
    def _product_for_plan(self, plan_code, company):
        code = self._param(PRODUCT_CODE_PARAM[plan_code], DEFAULT_PRODUCT_CODE[plan_code])
        product = self.env["product.product"].sudo().search(
            [("default_code", "=", code)], limit=1
        )
        if not product:
            raise UserError(
                _("No product with internal reference %(code)s exists for plan %(plan)s.")
                % {"code": code, "plan": plan_code}
            )
        if not product.is_recurring:
            raise UserError(
                _("Product %(code)s is not marked as recurring.") % {"code": code}
            )
        if product.company_id and product.company_id != company:
            raise UserError(
                _("Product %(code)s belongs to another company.") % {"code": code}
            )
        return product

    # -------------------------------------------------------------- validation

    @api.model
    def _validate(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_("The request body must be a JSON object."))

        unknown = sorted(set(payload) - ALLOWED_KEYS)
        if unknown:
            raise ValidationError(_("Unsupported request keys: %s") % ", ".join(unknown))
        # A key is missing only when it is absent/None/blank. A numeric 0 (or any other
        # falsy-but-supplied value) must reach the per-field checks below, otherwise
        # `quantity: 0` would be reported as a missing key instead of an out-of-range one.
        missing = sorted(
            key
            for key in REQUIRED_KEYS
            if payload.get(key) is None or str(payload.get(key)).strip() == ""
        )
        if missing:
            raise ValidationError(_("Missing required request keys: %s") % ", ".join(missing))

        data = {}

        tenant = str(payload["kartatap_company_id"]).strip()
        if not _SAFE_ID.match(tenant):
            raise ValidationError(_("kartatap_company_id has an invalid format."))
        data["kartatap_company_id"] = tenant

        request_id = str(payload["kartatap_request_id"]).strip()
        if not _REQUEST_ID.match(request_id):
            raise ValidationError(_("kartatap_request_id has an invalid format."))
        data["kartatap_request_id"] = request_id

        plan = str(payload["plan_code"]).strip().upper()
        if plan not in PLANS:
            raise ValidationError(_("plan_code must be one of SOLO, TEAM, BUSINESS."))
        data["plan_code"] = plan

        try:
            quantity = int(str(payload["quantity"]).strip())
        except (TypeError, ValueError):
            raise ValidationError(_("quantity must be a whole number."))
        if quantity < MIN_SEATS[plan]:
            raise ValidationError(
                _("Plan %(plan)s requires at least %(min)s seats.")
                % {"plan": plan, "min": MIN_SEATS[plan]}
            )
        if quantity > MAX_QUANTITY:
            raise ValidationError(_("quantity may not exceed %s.") % MAX_QUANTITY)
        data["quantity"] = quantity

        # Odoo is the pricing authority and bills in the KartaTap company's currency.
        # The requested currency is KartaTap's display selection: it is validated and
        # recorded on the order, and the response reports the currency actually billed,
        # so the customer always sees the real amount on the hosted payment page.
        currency = str(payload["currency"]).strip().upper()
        if not _CURRENCY.match(currency):
            raise ValidationError(_("currency must be a 3-letter ISO code."))
        data["currency"] = currency

        interval = str(payload.get("billing_interval") or "month").strip().lower()
        if interval not in BILLING_INTERVALS:
            raise ValidationError(_("billing_interval must be one of month, year."))
        data["billing_interval"] = interval

        company_name = str(payload["company_name"]).strip()
        if not 1 <= len(company_name) <= 120:
            raise ValidationError(_("company_name must be 1 to 120 characters."))
        data["company_name"] = company_name

        email = str(payload.get("admin_email") or "").strip()
        if email and not _EMAIL.match(email):
            raise ValidationError(_("admin_email has an invalid format."))
        data["admin_email"] = email

        country = str(payload.get("country_code") or "").strip().upper()
        if country and not _COUNTRY.match(country):
            raise ValidationError(_("country_code must be a 2-letter ISO code."))
        data["country_code"] = country

        for key in ("return_url", "cancel_url"):
            value = str(payload.get(key) or "").strip()
            if value:
                if len(value) > MAX_URL_LENGTH or not value.startswith("https://"):
                    raise ValidationError(_("%s must be a short https URL.") % key)
                allowed = {
                    h.strip().lower()
                    for h in (self._param("allowed_return_hosts") or "").split(",")
                    if h.strip()
                }
                host = value.split("/")[2].lower().split(":")[0] if "//" in value else ""
                if allowed:
                    if host not in allowed:
                        raise ValidationError(
                            _("%s host is not in the configured allowlist.") % key
                        )
                elif not host.endswith(KARTATAP_HOST_SUFFIX):
                    raise ValidationError(
                        _("%s must point at a KartaTap host.") % key
                    )
            data[key] = value

        return data

    # ------------------------------------------------------------------ public

    @api.model
    def create_or_get_kartatap_checkout(self, payload=None, **kwargs):
        """Atomic, idempotent entry point. Returns a sanitized JSON-serializable dict."""
        raw = dict(payload or {})
        raw.update({k: v for k, v in kwargs.items() if k not in raw})
        data = self._validate(raw)

        # Kill switch. Anything other than an explicit true disables checkout, so a typo
        # or a missing parameter can never re-open self-service billing by accident.
        if str(self._param("checkout_enabled", "False")).strip().lower() not in (
            "true",
            "1",
            "yes",
        ):
            raise UserError(_("KartaTap hosted checkout is currently disabled."))

        company = self._resolve_company()
        self = self.with_company(company)

        Order = self.env["sale.order"].sudo()
        existing = Order.search(
            [("kartatap_request_id", "=", data["kartatap_request_id"])], limit=1
        )
        if existing:
            return self._result(existing, deduplicated=True, partner_reused=True)

        partner, partner_reused = self._find_or_create_partner(data, company)
        order = self._create_order(data, partner, company)
        return self._result(order, deduplicated=False, partner_reused=partner_reused)

    # --------------------------------------------------------------- internals

    @api.model
    def _find_or_create_partner(self, data, company):
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search(
            [("kartatap_company_id", "=", data["kartatap_company_id"])], limit=1
        )
        if partner:
            return partner, True

        country = self.env["res.country"]
        if data["country_code"]:
            country = self.env["res.country"].sudo().search(
                [("code", "=", data["country_code"])], limit=1
            )

        partner = Partner.create(
            {
                "name": data["company_name"],
                "is_company": True,
                "company_type": "company",
                "company_id": company.id,
                "kartatap_company_id": data["kartatap_company_id"],
                "ref": data["kartatap_company_id"],
                "email": data["admin_email"] or False,
                "country_id": country.id if country else False,
            }
        )
        return partner, False

    @api.model
    def _create_order(self, data, partner, company):
        product = self._product_for_plan(data["plan_code"], company)
        period = self._period_for(data["billing_interval"])
        variant = product.product_variant_id

        pricing = variant.subscription_price_ids.filtered(lambda r: r.period_id == period)
        if not pricing and data["billing_interval"] != "month":
            # list_price is the monthly price; falling back to it would bill a whole
            # year at one month's price.
            raise UserError(
                _("Product %(code)s has no %(unit)s subscription price configured.")
                % {"code": product.default_code, "unit": data["billing_interval"]}
            )
        price_unit = pricing[:1].price if pricing else product.list_price

        order = self.env["sale.order"].sudo().create(
            {
                "partner_id": partner.id,
                "company_id": company.id,
                "currency_id": company.currency_id.id,
                # This checkout is API-driven: the customer never visits a portal
                # quotation page to click Accept & Sign, so Odoo's own
                # _check_amount_and_confirm_order() (sale/models/payment_transaction.py)
                # would otherwise refuse to auto-confirm the order on payment alone
                # (it requires not _has_to_be_signed()). A KartaTap-generated order
                # is authorized by the payment itself, not a portal signature.
                # Company-wide Sales settings (e.g. the default require_signature
                # for manually-created quotations) are intentionally left untouched.
                "require_signature": False,
                "kartatap_request_id": data["kartatap_request_id"],
                "kartatap_company_id": data["kartatap_company_id"],
                "recurrance_id": period.id,
                "client_order_ref": "KartaTap %s x%s" % (data["plan_code"], data["quantity"]),
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": data["quantity"],
                            "price_unit": price_unit,
                        },
                    )
                ],
            }
        )

        note_lines = [
            "KartaTap tenant: %s" % data["kartatap_company_id"],
            "KartaTap request: %s" % data["kartatap_request_id"],
            "Billing interval: %s" % data["billing_interval"],
            "Requested currency: %s (billed in %s)" % (data["currency"], company.currency_id.name),
        ]
        if data["return_url"]:
            note_lines.append("Return URL: %s" % data["return_url"])
        if data["cancel_url"]:
            note_lines.append("Cancel URL: %s" % data["cancel_url"])
        order.message_post(body="<br/>".join(note_lines))

        if order.state in ("draft", "sent"):
            order.action_quotation_sent()
        return order

    @api.model
    def _payment_link(self, order):
        """Build the hosted payment link for the order.

        Odoo's `payment.link.wizard` returns the document's own hosted link (for a sale
        order that is the token-authenticated customer-portal page, e.g.
        `<base>/my/orders/<id>?access_token=...&payment_amount=...`), so it must be used
        as-is and only validated:

        * the link must exist and be absolute;
        * when `sgc_kartatap_bridge.public_base_url` is configured (production MUST set
          it, e.g. https://app.sgctech.ai) the link must start with that base, so a
          misconfigured `web.base.url` can never send a customer to the wrong host;
        * otherwise only an absolute http(s) URL is accepted, which keeps local and
          staging runs working without weakening the production check.
        """
        wizard = (
            self.env["payment.link.wizard"]
            .sudo()
            .create(
                {
                    "res_model": "sale.order",
                    "res_id": order.id,
                    "amount": order.amount_total,
                    "amount_max": order.amount_total,
                    "currency_id": order.currency_id.id,
                    "partner_id": order.partner_invoice_id.id or order.partner_id.id,
                }
            )
        )
        link = (wizard.link or "").strip()
        if not link:
            raise UserError(_("Odoo did not return a payment link for this order."))

        expected_base = (self._param("public_base_url") or "").strip().rstrip("/")
        if expected_base:
            if not link.startswith(expected_base + "/"):
                raise UserError(
                    _(
                        "The payment link does not start with the configured public base URL "
                        "%(base)s; check the Odoo `web.base.url` system parameter."
                    )
                    % {"base": expected_base}
                )
        elif not link.startswith(("https://", "http://")):
            raise UserError(_("Odoo returned a payment link in an unexpected format."))
        return link

    def _result(self, order, deduplicated, partner_reused):
        line = order.order_line[:1]
        return {
            "ok": True,
            "deduplicated": bool(deduplicated),
            "partner_reused": bool(partner_reused),
            "checkout_url": self._payment_link(order),
            "amount": order.amount_total,
            "currency": order.currency_id.name,
            "plan_code": line.product_id.default_code or "",
            "quantity": int(sum(order.order_line.mapped("product_uom_qty"))),
            "odoo": {
                "partner_id": order.partner_id.id,
                "partner_kartatap_company_id": order.partner_id.kartatap_company_id or "",
                "sale_order_id": order.id,
                "sale_order_name": order.name,
                "sale_order_state": order.state,
                "subscription_period": order.recurrance_id.name or "",
                "billing_interval": order.recurrance_id.unit or "",
            },
        }
