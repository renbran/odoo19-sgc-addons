# -*- coding: utf-8 -*-
import logging
import re
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import email_normalize

from odoo.addons.sgc_accounting_clients.models.accounting_client import RESERVED_CODES

_logger = logging.getLogger(__name__)

# Package code -> (label, product xml id). Vol 2 price ladder, cheapest first.
PACKAGES = {
    "start": ("START", "product_acc_start"),
    "essential": ("ESSENTIAL", "product_acc_essential"),
    "compliance": ("COMPLIANCE", "product_acc_compliance"),
    "business": ("BUSINESS", "product_acc_business"),
    "growth_cfo": ("GROWTH CFO", "product_acc_growth_cfo"),
}
# Cycle -> (months covered, monthly fees charged). Annual prepayment is 12 for 11 (Vol 2).
CYCLES = {"monthly": (1, 1), "annual": (12, 11)}
EMIRATES = {
    "DU": "Dubai",
    "AZ": "Abu Dhabi",
    "SH": "Sharjah",
    "AJ": "Ajman",
    "UQ": "Umm Al Quwain",
    "RK": "Ras Al Khaimah",
    "FU": "Fujairah",
}
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{8,128}$")
VAT_RATE = 0.05
INTEGRATION_GROUP = "sgc_accounting_checkout.group_accounting_checkout_integration"
QUOTATION_VALID_DAYS = 30
MAX_CATCH_UP_PERIODS = 12  # ponytail: a client unbilled for over a year needs a human, not a loop
PARAM_ACCOUNT_MANAGER = "sgc_accounting_checkout.account_manager_login"


class SgcAccountingCheckout(models.TransientModel):
    """Website entry point (JSON-2, machine user in group_accounting_checkout_integration).

    Creates the customer and a Sign & Pay quotation. It never opens the portal: that
    happens on sale.order once the order is confirmed and paid (see _acc_activate).
    """

    _name = "sgc.accounting.checkout"
    _description = "Accounting package website checkout"

    @api.model
    def _validate(self, payload):
        p = dict(payload or {})

        def text(key, label, lo, hi, required=True):
            value = " ".join(str(p.get(key) or "").split())
            if not value and not required:
                return ""
            if not lo <= len(value) <= hi:
                raise ValidationError(
                    _("%(label)s must be %(lo)s to %(hi)s characters.", label=label, lo=lo, hi=hi)
                )
            return value

        request_id = str(p.get("request_id") or "")
        if not REQUEST_ID_RE.match(request_id):
            raise ValidationError(_("This signup link is invalid. Please reload the page and try again."))
        if p.get("package") not in PACKAGES:
            raise ValidationError(_("Please choose one of the published packages."))
        cycle = p.get("cycle") or "monthly"
        if cycle not in CYCLES:
            raise ValidationError(_("Please choose monthly or annual billing."))
        email = email_normalize(str(p.get("email") or ""))
        if not email or len(email) > 254:
            raise ValidationError(_("Please enter a valid email address."))
        trn = re.sub(r"\s", "", str(p.get("trn") or ""))
        if trn and not (len(trn) == 15 and trn.isdigit()):
            raise ValidationError(_("A UAE TRN must contain exactly 15 digits."))
        emirate = str(p.get("emirate") or "DU").upper()
        if emirate not in EMIRATES:
            raise ValidationError(_("Please choose an emirate."))
        return {
            "request_id": request_id,
            "package": p["package"],
            "cycle": cycle,
            "company_name": text("company_name", _("Company name"), 2, 120),
            "contact_name": text("contact_name", _("Contact name"), 2, 80),
            "email": email,
            "mobile": text("mobile", _("Mobile"), 6, 24, required=False),
            "trn": trn,
            "trade_licence_no": text("trade_licence_no", _("Trade licence number"), 2, 64, required=False),
            "emirate": emirate,
        }

    @api.model
    def create_checkout(self, payload=None, **kwargs):
        """Idempotent on request_id. Returns a JSON-serialisable dict."""
        # JSON-2 does not check model ACLs before the method runs, and everything below is sudo.
        if not (self.env.su or self.env.user.has_group(INTEGRATION_GROUP)):
            raise AccessError(_("Not allowed."))
        raw = dict(payload or {})
        raw.update({k: v for k, v in kwargs.items() if k not in raw})
        data = self._validate(raw)
        Order = self.env["sale.order"].sudo()
        existing = Order.search([("acc_request_id", "=", data["request_id"])], limit=1)
        if existing:
            if (existing.partner_id.email_normalized, existing.acc_package, existing.acc_cycle) != (
                data["email"], data["package"], data["cycle"]
            ):
                raise ValidationError(_("This signup form has changed. Please reload the page and submit again."))
            return self._result(existing, deduplicated=True)
        self._check_email_free(data["email"])
        # One payable accounting quotation per email: the latest submission replaces older ones,
        # so a second payment can never land on an order that cannot get a login.
        Order.search([
            ("acc_package", "!=", False),
            ("state", "in", ("draft", "sent")),
            ("partner_id.email_normalized", "=", data["email"]),
        ]).action_cancel()
        order = self._create_order(data, self._partner(data))
        return self._result(order, deduplicated=False)

    @api.model
    def _check_email_free(self, email):
        """An email that already has a login (any state) or a paid order awaiting its portal
        never gets a new self-serve workspace: re-activating or re-parenting an existing login
        would hand one customer's data to another. Those cases are handled by SGC staff."""
        users = self.env["res.users"].sudo().with_context(active_test=False).search(
            ["|", ("login", "=", email), ("partner_id.email_normalized", "=", email)]
        )
        if users.filtered(lambda u: not u.share):
            raise UserError(_("accounting_email_internal"))
        if users or self.env["sale.order"].sudo().search_count([
            ("acc_package", "!=", False),
            ("state", "=", "sale"),
            ("acc_client_id", "=", False),
            ("partner_id.email_normalized", "=", email),
        ]):
            raise UserError(_("accounting_email_exists"))

    @api.model
    def _partner(self, data):
        """A fresh company + contact; the contact will own the portal login (login = email)."""
        Partner = self.env["res.partner"].sudo()
        country = self.env.ref("base.ae", raise_if_not_found=False)
        # UAE VAT is applied by per-emirate fiscal positions matched on the state; a partner
        # without one falls through to the "Non-UAE" position (0%).
        state = country and self.env["res.country.state"].search(
            [("country_id", "=", country.id), ("code", "=", data["emirate"])], limit=1
        )
        company = Partner.create({
            "name": data["company_name"],
            "is_company": True,
            "email": data["email"],
            "phone": data["mobile"] or False,
            "country_id": country.id if country else False,
            "state_id": state.id if state else False,
        })
        return Partner.create({
            "name": data["contact_name"],
            "parent_id": company.id,
            "type": "contact",
            "email": data["email"],
            "phone": data["mobile"] or False,
        })

    @api.model
    def _create_order(self, data, partner):
        label, xmlid = PACKAGES[data["package"]]
        months, charged = CYCLES[data["cycle"]]
        package = self.env.ref("sgc_accounting_checkout.%s" % xmlid)
        onboarding = self.env.ref("sgc_accounting_checkout.product_acc_onboarding")
        if data["cycle"] == "annual":
            line_name = _("Accounting package %(p)s - 12 months, annual prepayment (12 for the price of 11)", p=label)
        else:
            line_name = _("Accounting package %(p)s - first month", p=label)
        order = self.env["sale.order"].sudo().create({
            "partner_id": partner.id,
            "company_id": self.env.company.id,
            "require_signature": True,
            "require_payment": True,
            "prepayment_percent": 1.0,
            "validity_date": fields.Date.context_today(self) + timedelta(days=QUOTATION_VALID_DAYS),
            "client_order_ref": "Accounting %s" % label,
            "acc_request_id": data["request_id"],
            "acc_package": data["package"],
            "acc_cycle": data["cycle"],
            "acc_company_name": data["company_name"],
            "acc_trn": data["trn"] or False,
            "acc_trade_licence_no": data["trade_licence_no"] or False,
            "acc_emirate": EMIRATES[data["emirate"]],
            "note": self._terms(label, data["cycle"]),
            "order_line": [
                Command.create({"product_id": package.id, "product_uom_qty": charged, "name": line_name}),
                Command.create({"product_id": onboarding.id, "product_uom_qty": 1}),
            ],
        })
        # Never take money at a wrong price: a missing price or VAT other than 5% is a setup fault.
        if any(line.price_unit <= 0 for line in order.order_line):
            raise UserError(_("accounting_price_missing"))
        if abs(order.amount_tax - order.amount_untaxed * VAT_RATE) > 0.05:
            raise UserError(_("accounting_tax_missing"))
        order.action_quotation_sent()  # 'sent' exposes Sign & Pay on the portal page
        return order

    @api.model
    def _terms(self, label, cycle):
        rows = [
            _("Package: %s. No free trial: your accounting portal opens as soon as this order is paid.") % label,
            _("Annual prepayment: 12 months for the price of 11, renewed yearly.") if cycle == "annual"
            else _("Monthly package: from month 2 the fee is invoiced monthly in advance; cancel with 30 days' notice."),
            _("One-time onboarding and system setup: AED 500."),
            _("Additional users: USD 7 per user per month. Extra bank accounts: AED 35 per account per month. "
              "Within-package overage: AED 4.50 per transaction, always after a written upgrade recommendation."),
            _("Catch-up bookkeeping and out-of-scope work are quoted separately."),
            _("All amounts are in AED and exclusive of 5% VAT."),
        ]
        return Markup("<p>%s</p>") % Markup("</p><p>").join(rows)

    @api.model
    def _result(self, order, deduplicated):
        return {
            "ok": True,
            "deduplicated": bool(deduplicated),
            "checkout_url": order._acc_public_url() + order.get_portal_url(),
            "sale_order_name": order.name,
            "amount_untaxed": order.amount_untaxed,
            "amount_tax": order.amount_tax,
            "amount_total": order.amount_total,
            "currency": order.currency_id.name,
            "package": order.acc_package,
            "cycle": order.acc_cycle,
        }


class SaleOrder(models.Model):
    _inherit = "sale.order"

    acc_request_id = fields.Char("Accounting signup request", copy=False, readonly=True, index=True)
    acc_package = fields.Selection(
        [(code, label) for code, (label, _xmlid) in PACKAGES.items()],
        string="Accounting package", copy=False, readonly=True,
    )
    acc_cycle = fields.Selection(
        [("monthly", "Monthly"), ("annual", "Annual (12 for 11)")],
        string="Accounting billing", copy=False, readonly=True,
    )
    acc_company_name = fields.Char("Accounting client name", copy=False)
    acc_trn = fields.Char("Accounting client TRN", copy=False)
    acc_trade_licence_no = fields.Char("Accounting client trade licence", copy=False)
    acc_emirate = fields.Char("Accounting client emirate", copy=False)
    acc_client_id = fields.Many2one("sgc.accounting.client", "Accounting workspace", copy=False, readonly=True, index=True)
    acc_activation_error = fields.Text("Accounting portal error", copy=False, readonly=True)
    acc_paid_until = fields.Date(
        "Accounting invoiced until", copy=False,
        help="End of the last invoiced period. The next renewal invoice is issued on this date.",
    )
    acc_billing_day = fields.Integer(
        "Accounting billing day", copy=False,
        help="Day of month the periods start on (clamped to short months), so 31st stays 31st.",
    )
    acc_renewal_active = fields.Boolean(
        "Accounting renewals", copy=False,
        help="Untick when the client has given notice: no further renewal invoices are issued.",
    )

    _acc_request_id_uniq = models.Constraint(
        "unique(acc_request_id)", "An order already exists for this accounting signup."
    )

    def _acc_is_paid(self):
        """A settled online payment or a paid customer invoice. A confirmed order alone is
        not enough: an order can be confirmed by hand without any money arriving."""
        self.ensure_one()
        order = self.sudo()
        covers = lambda amount: order.currency_id.compare_amounts(amount, order.amount_total) >= 0  # noqa: E731
        txs = order.transaction_ids.filtered(lambda tx: tx.state == "done" and tx.currency_id == order.currency_id)
        if covers(sum(txs.mapped("amount"))):
            return True
        invoices = order.invoice_ids.filtered(lambda m: m.move_type == "out_invoice" and m.state == "posted")
        return bool(invoices) and all(m.payment_state in ("paid", "in_payment") for m in invoices) and covers(
            sum(invoices.mapped("amount_total"))
        )

    def action_confirm(self):
        res = super().action_confirm()
        # Payment post-processing confirms the order with the transaction already 'done',
        # so the portal opens in the same request. Anything else is picked up by the cron.
        self.filtered("acc_package")._acc_activate()
        return res

    @api.model
    def _acc_cron_activate(self):
        self.sudo().search([
            ("acc_package", "!=", False),
            ("acc_client_id", "=", False),
            ("state", "=", "sale"),
        ])._acc_activate()

    def _acc_activate(self):
        for order in self.sudo():
            if order.acc_client_id or order.state != "sale" or not order._acc_is_paid():
                continue
            try:
                with self.env.cr.savepoint():
                    order._acc_open_portal()
            except Exception as err:  # never break payment confirmation; the cron retries
                message = str(err)[:500]
                if order.acc_activation_error == message:
                    _logger.info("Accounting portal for %s still not opened: %s", order.name, message)
                else:
                    _logger.exception("Accounting portal for %s not opened", order.name)
                    order.acc_activation_error = message
                    order.message_post(body=_(
                        "The accounting portal could not be opened yet: %(error)s. It is retried every 10 minutes.",
                        error=message,
                    ))

    def _acc_open_portal(self):
        self.ensure_one()
        Client = self.env["sgc.accounting.client"].sudo()
        name = self.acc_company_name or self.partner_id.commercial_partner_id.name
        client = Client.create({
            "name": name,
            "legal_name": name,
            "client_code": self._acc_client_code(name),
            "partner_id": self.partner_id.commercial_partner_id.id,
            "trn": self.acc_trn or False,
            "vat_registered": bool(self.acc_trn),
            "trade_license_no": self.acc_trade_licence_no or False,
            "emirate": self.acc_emirate or False,
            "currency_id": self.currency_id.id,
            "account_manager_id": self._acc_account_manager().id,
        })
        months, _charged = CYCLES[self.acc_cycle]
        today = fields.Date.context_today(self)
        self.write({
            "acc_client_id": client.id,
            "acc_activation_error": False,
            # The checkout paid the first period; renewals start when it ends.
            "acc_billing_day": today.day,
            "acc_paid_until": today + relativedelta(months=months),
            "acc_renewal_active": True,
        })
        client.action_queue_provision()  # status 'queued' + event for the accounting receiver
        client.message_post(body=_(
            "Opened from paid order %(order)s: package %(package)s, %(cycle)s billing.",
            order=self.name,
            package=dict(self._fields["acc_package"].selection)[self.acc_package],
            cycle=dict(self._fields["acc_cycle"].selection)[self.acc_cycle],
        ))
        self.message_post(body=_("Accounting portal opened: workspace %s.", client.client_code))
        self._acc_grant_portal(client)  # last: it sends the invitation email immediately

    @api.model
    def _acc_cron_renew(self, today=None):
        """Daily: invoice every period that has started and is not yet invoiced (catches up
        missed days), post it and queue the standard invoice email, which carries the pay link."""
        today = today or fields.Date.context_today(self)
        template = self.env.ref("account.email_template_edi_invoice", raise_if_not_found=False)
        orders = self.sudo().search([
            ("acc_client_id", "!=", False),
            ("acc_renewal_active", "=", True),
            ("acc_paid_until", "<=", today),
        ])
        for order in orders:
            client = order.acc_client_id
            if not client.active or client.status in ("suspended", "archived"):
                continue
            try:
                with self.env.cr.savepoint():
                    invoices = order._acc_issue_renewals(today)
            except Exception:  # one order must not stop the others; retried tomorrow
                _logger.exception("Accounting renewal for %s failed", order.name)
                continue
            for invoice in invoices:  # queued, not sent inline: a bad address never undoes an invoice
                try:
                    if template:
                        template.send_mail(invoice.id)
                        invoice.is_move_sent = True
                except Exception:
                    _logger.exception("Accounting renewal invoice %s not emailed", invoice.name)

    def _acc_issue_renewals(self, today):
        self.ensure_one()
        months, charged = CYCLES[self.acc_cycle]
        label, xmlid = PACKAGES[self.acc_package]
        product = self.env.ref("sgc_accounting_checkout.%s" % xmlid)
        Move = self.env["account.move"].with_company(self.company_id)
        invoices = Move
        for _i in range(MAX_CATCH_UP_PERIODS):
            start = self.acc_paid_until
            if start > today:
                break
            end = start + relativedelta(months=months, day=self.acc_billing_day or start.day)
            invoices |= Move.create({
                "move_type": "out_invoice",
                "partner_id": self.partner_invoice_id.id,
                "company_id": self.company_id.id,
                "currency_id": self.currency_id.id,
                "fiscal_position_id": self.fiscal_position_id.id,
                "invoice_payment_term_id": self.payment_term_id.id,
                "invoice_origin": self.name,
                "invoice_date": today,
                "invoice_line_ids": [Command.create({
                    "product_id": product.id,
                    "quantity": charged,
                    "price_unit": product.lst_price,
                    "name": _("Accounting package %(p)s, %(start)s to %(end)s", p=label, start=start,
                              end=end - relativedelta(days=1)),
                })],
            })
            self.acc_paid_until = end
        invoices.action_post()
        if invoices:
            self.message_post(body=_("Renewal invoices issued: %s.", ", ".join(invoices.mapped("name"))))
        return invoices

    def _acc_public_url(self):
        # Same public host as the Layer 3 Sign & Pay links (web.base.url can be internal).
        base = self.env["ir.config_parameter"].sudo().get_param("sgc_layer3_bridge.public_base_url") or ""
        return base.strip().rstrip("/") or self.get_base_url()

    def _acc_account_manager(self):
        login = self.env["ir.config_parameter"].sudo().get_param(PARAM_ACCOUNT_MANAGER)
        manager = login and self.env["res.users"].sudo().search([("login", "=", login), ("share", "=", False)], limit=1)
        return manager or self.user_id

    def _acc_grant_portal(self, client):
        contact = self.partner_id
        # Never re-activate or re-group an existing login (revoked users stay revoked).
        if contact.with_context(active_test=False).user_ids:
            raise UserError(_("%s already has a login; SGC staff must link this workspace by hand.") % contact.email)
        wizard = self.env["portal.wizard"].sudo().create({
            "partner_ids": [Command.set(contact.ids)],
            "welcome_message": _(
                "Your SGC accounting portal for %(name)s is ready. Set your password, then open "
                "%(url)s/my/accounting to upload your onboarding documents.",
                name=client.name, url=self._acc_public_url(),
            ),
        })
        wizard.user_ids.filtered(lambda w: w.partner_id == contact).action_grant_access()
        # The login it was registered with is the subscription's only portal access.
        client.owner_user_id = contact.user_ids[:1]

    @api.model
    def _acc_client_code(self, name):
        """2-32 chars, [a-z0-9-], unique, not reserved (sgc.accounting.client rule)."""
        base = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:24].strip("-")
        if len(base) < 2 or base in RESERVED_CODES:
            base = ("client-" + base).strip("-")
        Client = self.env["sgc.accounting.client"].sudo().with_context(active_test=False)
        code, n = base, 1
        while Client.search_count([("client_code", "=", code)]):
            n += 1
            code = "%s-%d" % (base, n)
        return code
