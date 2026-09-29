import base64
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..lib import lifecycle

_logger = logging.getLogger(__name__)

PARAM_PREFIX = "sgc_layer3_bridge."

L3_STATES = [
    ("awaiting_payment", "Awaiting payment"),
    ("active", "Active"),
    ("grace", "Grace"),
    ("read_only", "Read-only"),
    ("archive", "Archive"),
    ("deleted", "Deleted"),
]
DOCS_STATUSES = [
    ("pending", "Pending upload"),
    ("submitted", "Submitted - to review"),
    ("rejected", "Rejected"),
    ("approved", "Approved"),
    ("expiring", "Licence expiring"),
]
CYCLES = [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("half_yearly", "Half-yearly"), ("annual", "Annual")]
CYCLE_MONTHS = {"monthly": 1, "quarterly": 3, "half_yearly": 6, "annual": 12}
INCLUDED_USERS = 5
LICENCE_WARNING_DAYS = 30
MAX_CATCH_UP_PERIODS = 12  # at most a year of missed monthly renewals per run
QUOTATION_VALID_DAYS = 7


class SaleOrder(models.Model):
    _inherit = "sale.order"

    l3_request_id = fields.Char("Layer 3 Request ID", index=True, copy=False)
    l3_tenant_slug = fields.Char("Tenant subdomain", index=True, copy=False)
    l3_cycle = fields.Selection(CYCLES, string="Billing cycle", copy=False)
    l3_users = fields.Integer("Licensed users", copy=False)
    l3_founding = fields.Boolean("Founding cohort", copy=False)
    l3_admin_name = fields.Char("Tenant admin name", copy=False)
    l3_admin_email = fields.Char("Tenant admin email", copy=False)
    l3_mobile = fields.Char("Mobile", copy=False)
    l3_trade_licence_no = fields.Char("Trade licence no.", copy=False)
    l3_state = fields.Selection(L3_STATES, string="Account state", copy=False, index=True, tracking=True)
    l3_state_reason = fields.Char("State reason", copy=False, readonly=True)
    l3_state_since = fields.Date("In this state since", copy=False, readonly=True)
    l3_state_version = fields.Integer("Sync version", copy=False, readonly=True)
    l3_activated_on = fields.Date("Activated on", copy=False, readonly=True)
    l3_docs_status = fields.Selection(DOCS_STATUSES, string="Documents", copy=False, tracking=True)
    l3_docs_reason = fields.Char("Rejection reason", copy=False)
    l3_licence_expiry = fields.Date("Licence expiry", copy=False)
    l3_licence_attachment_id = fields.Many2one("ir.attachment", string="Trade licence copy", copy=False)
    l3_notice_date = fields.Date("Notice given on", copy=False, readonly=True)
    l3_end_date = fields.Date("Cancellation effective", copy=False, readonly=True)
    l3_tenant_url = fields.Char("Workspace", compute="_compute_l3_tenant_url")

    _l3_request_id_uniq = models.Constraint(
        "unique(l3_request_id)",
        "An order already exists for this Layer 3 request ID.",
    )

    @api.depends("l3_tenant_slug")
    def _compute_l3_tenant_url(self):
        for order in self:
            order.l3_tenant_url = (
                "https://%s.sgctech.ai" % order.l3_tenant_slug if order.l3_tenant_slug else False
            )

    # ------------------------------------------------------------------ config

    @api.model
    def _l3_param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _l3_float(self, key, default):
        try:
            return float(self._l3_param(key, default))
        except (TypeError, ValueError):
            return float(default)

    @api.model
    def _l3_cycle_price(self, cycle, monthly):
        """Price for one billing cycle: monthly x months, less the cycle rebate (OIC item 2)."""
        rebate = self._l3_float("rebate_%s" % cycle, {"monthly": 0, "quarterly": 0, "half_yearly": 2.5, "annual": 5}[cycle])
        return round(monthly * CYCLE_MONTHS[cycle] * (1 - rebate / 100.0), 2)

    @api.model
    def _l3_products(self):
        return {
            "base": self.env.ref("sgc_layer3_bridge.product_l3_base"),
            "user_founding": self.env.ref("sgc_layer3_bridge.product_l3_user_founding"),
            "user_standard": self.env.ref("sgc_layer3_bridge.product_l3_user_standard"),
        }

    @api.model
    def _l3_period(self, cycle):
        return self.env.ref("sgc_layer3_bridge.period_l3_%s" % cycle)

    def _l3_line_price(self, product):
        """Unit price for a Layer 3 line on this order, or None if not a Layer 3 product."""
        self.ensure_one()
        products = self._l3_products()
        if product == products["base"]:
            monthly = self._l3_float("base_monthly", 875)
        elif product == products["user_founding"]:
            monthly = self._l3_float("user_monthly_founding", 50)
        elif product == products["user_standard"]:
            monthly = self._l3_float("user_monthly_standard", 75)
        else:
            return None
        return self._l3_cycle_price(self.l3_cycle, monthly)

    # ------------------------------------------------------------ evaluation

    def _l3_is_paid(self):
        """A settled online payment or a paid customer invoice. A confirmed order alone is
        not enough: an order can be confirmed by hand without any money arriving."""
        self.ensure_one()
        if self.sudo().transaction_ids.filtered(lambda tx: tx.state == "done"):
            return True
        return bool(
            self.invoice_ids.filtered(
                lambda m: m.move_type == "out_invoice"
                and m.state == "posted"
                and m.payment_state in ("paid", "in_payment")
            )
        )

    def _l3_days_overdue(self, today):
        self.ensure_one()
        unpaid = self.invoice_ids.filtered(
            lambda m: m.move_type == "out_invoice"
            and m.state == "posted"
            and m.payment_state in ("not_paid", "partial")
            and m.invoice_date_due
            and m.invoice_date_due < today
        )
        if not unpaid:
            return 0
        return (today - min(unpaid.mapped("invoice_date_due"))).days

    def _l3_set_state(self, state, reason, today):
        self.ensure_one()
        self.write(
            {
                "l3_state": state,
                "l3_state_reason": reason,
                "l3_state_since": today,
            }
        )
        self._l3_sync()

    def _l3_sync(self, provision=False):
        """Bump the sync version and queue a snapshot for the tenant receiver."""
        for order in self:
            if order.l3_state in (False, "awaiting_payment"):
                continue
            if not order.l3_state_version:
                # The receiver ignores any version it has already seen for a subdomain, so a
                # new order for a subdomain used before (a client coming back after deletion)
                # continues from the earlier order's last version instead of restarting at 1.
                earlier = self.sudo().search(
                    [("l3_tenant_slug", "=", order.l3_tenant_slug), ("id", "!=", order.id)],
                    order="l3_state_version desc", limit=1,
                )
                order.l3_state_version = earlier.l3_state_version
            order.l3_state_version += 1
            self.env["layer3.event"]._enqueue(order, provision=provision)

    @api.model
    def _l3_update_states(self, today=None):
        today = today or fields.Date.context_today(self)
        archive_days = int(self._l3_float("archive_days", 60))  # MSA Rev3 s.6: deletion 60 days after Archive
        orders = self.sudo().search(
            [
                ("l3_tenant_slug", "!=", False),
                ("state", "=", "sale"),
                ("l3_state", "!=", "deleted"),
            ],
            order="id",
        )
        for order in orders:
            activated = bool(order.l3_activated_on)
            if not activated and order._l3_is_paid():
                order.write({"l3_activated_on": today, "l3_state": "active", "l3_state_reason": "paid", "l3_state_since": today})
                order._l3_sync(provision=True)
                continue
            state, reason = lifecycle.target_state(
                today=today,
                activated=activated,
                days_overdue=order._l3_days_overdue(today),
                end_date=order.l3_end_date,
                archive_since=order.l3_state_since if order.l3_state == "archive" else None,
                archive_days=archive_days,
            )
            if state and (state, reason) != (order.l3_state, order.l3_state_reason):
                order._l3_set_state(state, reason, today)

    @api.model
    def _l3_catch_up_renewals(self, today=None):
        """Issue renewals that sttl_sale_subscription missed.

        sttl's daily job only renews orders whose next_invoice_date is exactly today, so a day
        on which it did not run (outage, restart) would silently end a subscription's billing.
        This repeats sttl's own steps for any running Layer 3 subscription whose date has
        passed: bump the recurring service lines, invoice, post (sttl's action_post moves
        next_invoice_date on by one period). It never touches today's renewals.
        """
        today = today or fields.Date.context_today(self)
        orders = self.sudo().search(
            [
                ("l3_tenant_slug", "!=", False),
                ("state", "=", "sale"),
                ("subscription_status", "=", "b"),
                ("next_invoice_date", "<", today),
                ("l3_state", "!=", "deleted"),
            ],
            order="id",
        )
        for order in orders:
            try:
                with self.env.cr.savepoint():
                    for _i in range(MAX_CATCH_UP_PERIODS):
                        due = order.next_invoice_date
                        if not due or due >= today or order.subscription_status != "b":
                            break
                        for line in order.order_line:
                            product = line.product_id
                            if (
                                product.is_recurring
                                and product.type == "service"
                                and product.invoice_policy == "order"
                                and line.invoice_status != "to invoice"
                            ):
                                if not line.prev_added_qty:
                                    line.prev_added_qty = line.product_uom_qty
                                line.product_uom_qty += line.prev_added_qty
                        if order.invoice_status != "to invoice":
                            break
                        invoice = order._create_invoices()
                        invoice.action_post()
                        if order.recurr_until and order.next_invoice_date and order.recurr_until <= order.next_invoice_date:
                            order.subscription_status = "c"
                        if order.next_invoice_date == due:
                            break  # sttl did not move the date on; never loop on the same period
                        order.message_post(
                            body=_("Layer 3: issued the renewal due on %(due)s that the subscription job missed (%(inv)s).")
                            % {"due": due, "inv": invoice.name}
                        )
            except Exception:  # noqa: BLE001 - one order must not stop the others
                _logger.exception("Layer 3: catching up the renewal of %s failed", order.name)

    @api.model
    def _l3_expire_quotations(self, today=None):
        """Cancel unpaid Layer 3 quotations past their validity so the subdomain is freed."""
        today = today or fields.Date.context_today(self)
        stale = self.sudo().search(
            [
                ("l3_tenant_slug", "!=", False),
                ("state", "in", ("draft", "sent")),
                ("validity_date", "<", today),
            ]
        )
        for order in stale:
            if order.transaction_ids.filtered(lambda tx: tx.state in ("pending", "authorized", "done")):
                continue
            order._action_cancel()
            if order.partner_id.l3_tenant_slug == order.l3_tenant_slug and not self.search_count(
                [("partner_id", "=", order.partner_id.id), ("state", "=", "sale")]
            ):
                order.partner_id.l3_tenant_slug = False

    @api.model
    def _l3_mail_new_invoices(self):
        """Send each posted Layer 3 invoice to the customer once (renewals included)."""
        template = self.env.ref("account.email_template_edi_invoice", raise_if_not_found=False)
        if not template:
            return
        orders = self.sudo().search([("l3_tenant_slug", "!=", False), ("state", "=", "sale")])
        invoices = orders.invoice_ids.filtered(
            lambda m: m.move_type == "out_invoice" and m.state == "posted" and not m.is_move_sent
        )
        for invoice in invoices:
            try:
                template.send_mail(invoice.id)
                invoice.is_move_sent = True
            except Exception:  # noqa: BLE001 - one bad address must not stop the rest
                _logger.exception("Layer 3: could not email invoice %s", invoice.name)

    @api.model
    def _l3_licence_expiry(self, today=None):
        today = today or fields.Date.context_today(self)
        soon = today + timedelta(days=LICENCE_WARNING_DAYS)
        orders = self.sudo().search(
            [
                ("l3_tenant_slug", "!=", False),
                ("l3_docs_status", "=", "approved"),
                ("l3_licence_expiry", "!=", False),
                ("l3_licence_expiry", "<=", soon),
            ]
        )
        for order in orders:
            order.l3_docs_status = "expiring"
            order._l3_review_activity(_("Trade licence expires on %s") % order.l3_licence_expiry)
            order._l3_sync()

    @api.model
    def _l3_cron(self):
        self._l3_expire_quotations()
        self._l3_catch_up_renewals()
        self._l3_update_states()
        self._l3_licence_expiry()
        self._l3_mail_new_invoices()

    # --------------------------------------------------------------- documents

    def _l3_review_activity(self, note):
        """Put the document check on SGC's to-do list (the 'warning to us')."""
        self.ensure_one()
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        self.activity_schedule(
            activity_type_id=activity_type.id if activity_type else False,
            summary=_("Layer 3: check trade licence"),
            note=note,
            user_id=self.user_id.id or self.env.ref("base.user_admin").id,
        )

    def _l3_submit_documents(self, data, filename, mimetype, licence_no, expiry):
        """Store an uploaded trade licence. Never changes the account state."""
        self.ensure_one()
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": filename or "trade-licence",
                "datas": base64.b64encode(data),
                "mimetype": mimetype,
                "res_model": "sale.order",
                "res_id": self.id,
            }
        )
        self.sudo().write(
            {
                "l3_licence_attachment_id": attachment.id,
                "l3_trade_licence_no": licence_no or self.l3_trade_licence_no,
                "l3_licence_expiry": expiry,
                "l3_docs_status": "submitted",
                "l3_docs_reason": False,
            }
        )
        self.message_post(body=_("Trade licence uploaded by the customer (%s).") % attachment.name, attachment_ids=[attachment.id])
        self._l3_review_activity(_("Review the uploaded trade licence."))
        self._l3_sync()

    def action_l3_docs_approve(self):
        for order in self:
            if not order.l3_licence_expiry:
                raise UserError(_("Enter the trade licence expiry date before approving."))
            order.write({"l3_docs_status": "approved", "l3_docs_reason": False})
            order.activity_feedback(["mail.mail_activity_data_todo"], feedback=_("Trade licence approved"))
            order._l3_sync()
        return True

    def action_l3_docs_reject(self):
        for order in self:
            if not order.l3_docs_reason:
                raise UserError(_("Write the rejection reason first; the customer sees it."))
            order.write({"l3_docs_status": "rejected"})
            order._l3_sync()
        return True

    # ------------------------------------------------------------ cancellation

    def _l3_give_notice(self, notice_date):
        """Record the client's notice (MSA 13.3): effective at the end of a billing cycle at
        least 60 days away. No refund; invoicing stops after that cycle."""
        self.ensure_one()
        if self.l3_notice_date:
            return self.l3_end_date
        if self.state != "sale" or not self.l3_activated_on:
            raise UserError(_("Only an active subscription can be cancelled."))
        Move = self.env["account.move"]
        cycle_end = self.next_invoice_date or Move._compute_next_invoice_date(notice_date, self.recurrance_id)
        end = lifecycle.notice_end_date(
            notice_date, cycle_end, lambda d: Move._compute_next_invoice_date(d, self.recurrance_id)
        )
        vals = {"l3_notice_date": notice_date, "l3_end_date": end}
        if self.next_invoice_date and end <= self.next_invoice_date:
            vals["subscription_status"] = "c"  # the current cycle is the last one billed
        else:
            vals["recurr_until"] = end - timedelta(days=1)
        self.sudo().write(vals)
        self.message_post(body=_("Customer gave notice on %(n)s. Cancellation takes effect on %(e)s.") % {"n": notice_date, "e": end})
        return end


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _compute_price_unit(self):
        """Layer 3 lines are always priced from the Layer 3 parameters.

        `sttl_sale_subscription` resets price_unit from its own pricing table on every
        recompute (including the quantity bump on each recurring invoice). Layer 3 does not
        use that table, so this runs after it and restores the contract price.
        """
        super()._compute_price_unit()
        for line in self:
            order = line.order_id
            if order.l3_tenant_slug and order.l3_cycle and line.product_id:
                price = order._l3_line_price(line.product_id)
                if price is not None:
                    line.price_unit = price
