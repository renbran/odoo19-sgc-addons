import json
import logging
import re
import time
from datetime import datetime, timedelta

import requests

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError

from ..lib import entitlement_contract as contract

_logger = logging.getLogger(__name__)

PARAM_PREFIX = "sgc_kartatap_bridge."
DEFAULT_ENDPOINT = "https://card.kartatap.com/api/integrations/odoo/entitlements"
HTTP_TIMEOUT_SECONDS = 8
DELIVERY_BATCH = 10
RECONCILE_LIMIT = 500
_ERROR_CODE = re.compile(r"^[a-z0-9_]{1,48}$")


class KartatapEntitlementEvent(models.Model):
    """Durable outbox for the Odoo -> KartaTap entitlement feed.

    Odoo is the financial system of record; KartaTap only learns that a tenant paid,
    renewed, fell behind or ended its subscription from these signed events. Each
    event is written here first (its body frozen as the exact bytes that will be
    signed) and delivered by the `_cron_process` job, so a KartaTap outage, a
    network fault or a restart never loses one:

    * delivery is at-least-once; the receiver is idempotent on `event_id` and
      acknowledges a replay of the same bytes with 2xx;
    * events for one KartaTap tenant are delivered strictly in order: a later event
      waits while an earlier one for the same tenant is still pending;
    * transient failures (network, 408/429/5xx) back off per
      `entitlement_contract.BACKOFF_SECONDS`, then dead-letter;
    * a refused event (any other 4xx) is never re-sent automatically;
    * nothing is enqueued or sent unless `entitlement_push_enabled` is true and a
      signing secret is configured.

    Events are derived by `_reconcile`, which scans KartaTap-originated orders on
    every run. Deterministic event ids make that scan idempotent, so it also
    catches up on anything that happened while the push was disabled.
    """

    _name = "kartatap.entitlement.event"
    _description = "KartaTap entitlement event (outbox)"
    _order = "id desc"
    _rec_name = "event_id"

    event_id = fields.Char(required=True, index=True, readonly=True, copy=False)
    event_type = fields.Char(required=True, readonly=True)
    kartatap_company_id = fields.Char(required=True, index=True, readonly=True)
    order_id = fields.Many2one("sale.order", ondelete="set null", index=True, readonly=True)
    body = fields.Text(required=True, readonly=True, help="Exact JSON bytes that are signed and sent.")
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Delivered"),
            ("rejected", "Rejected by KartaTap"),
            ("dead", "Dead-lettered"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    last_status_code = fields.Integer(readonly=True)
    last_error = fields.Char(readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _event_id_uniq = models.Constraint(
        "unique(event_id)",
        "An entitlement event with this id already exists.",
    )

    # ------------------------------------------------------------------ config

    @api.model
    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _push_enabled(self):
        return str(self._param("entitlement_push_enabled", "False")).strip().lower() in ("true", "1", "yes")

    @api.model
    def _delivery_config(self):
        """(endpoint, secret) or None. Logs why, never the values themselves."""
        endpoint = (self._param("entitlement_endpoint") or DEFAULT_ENDPOINT).strip()
        if not endpoint.startswith("https://") or "@" in endpoint.split("/")[2]:
            _logger.error("KartaTap entitlement push: the endpoint must be an https URL without credentials.")
            return None
        secret = (self._param("entitlement_signing_secret") or "").strip()
        if len(secret) < contract.MIN_SECRET_LENGTH:
            _logger.error(
                "KartaTap entitlement push: %sentitlement_signing_secret is missing or shorter than %s characters.",
                PARAM_PREFIX,
                contract.MIN_SECRET_LENGTH,
            )
            return None
        return endpoint, secret

    # -------------------------------------------------------------- derivation

    @api.model
    def _plan_codes(self):
        """product default_code -> KartaTap plan, from the checkout's own parameters."""
        checkout = self.env["kartatap.checkout"]
        from .kartatap_checkout import DEFAULT_PRODUCT_CODE, PRODUCT_CODE_PARAM

        return {
            checkout._param(PRODUCT_CODE_PARAM[plan], DEFAULT_PRODUCT_CODE[plan]): plan
            for plan in contract.PLANS
        }

    @api.model
    def _plan_and_quantity(self, order):
        codes = self._plan_codes()
        plan_lines = order.order_line.filtered(lambda l: l.product_id.default_code in codes)
        plans = set(codes[l.product_id.default_code] for l in plan_lines)
        if len(plans) != 1:
            raise contract.ContractError("order must carry exactly one KartaTap plan")
        # sttl_sale_subscription grows product_uom_qty on each recurring invoice for
        # ordered-quantity products and keeps the original in prev_added_qty, so the
        # billed seat count is prev_added_qty when set.
        quantity = int(sum(l.prev_added_qty or l.product_uom_qty for l in plan_lines))
        return plans.pop(), quantity

    @api.model
    def _event_id(self, order, kind, discriminator=None):
        db_uuid = (self.env["ir.config_parameter"].sudo().get_param("database.uuid") or "db")[:8]
        parts = ["odoo", db_uuid, "so%s" % order.id, kind]
        if discriminator:
            parts.append(discriminator)
        return ":".join(parts)

    @staticmethod
    def _as_datetime(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        return datetime.combine(value, datetime.min.time())

    @api.model
    def _period_end(self, order, start_date):
        if order.next_invoice_date:
            return self._as_datetime(order.next_invoice_date)
        if order.recurrance_id and start_date:
            next_date = self.env["account.move"]._compute_next_invoice_date(start_date, order.recurrance_id)
            return self._as_datetime(next_date)
        return None

    @api.model
    def _enqueue(self, order, kind, occurred_at, discriminator=None, period_end=None, reason_code=None):
        event_id = self._event_id(order, kind, discriminator)
        if self.sudo().search_count([("event_id", "=", event_id)]):
            return self.browse()
        try:
            plan, quantity = self._plan_and_quantity(order)
            payload = contract.build_payload(
                event_id=event_id,
                event_type="subscription.%s" % kind,
                occurred_at=occurred_at,
                kartatap_company_id=order.kartatap_company_id,
                plan_code=plan,
                quantity=quantity,
                odoo_partner_ref="res.partner:%s" % order.partner_id.id,
                odoo_subscription_ref="sale.order:%s" % order.id,
                effective_period_end=period_end,
                reason_code=reason_code,
            )
        except contract.ContractError as exc:
            _logger.warning("KartaTap entitlement event %s not queued: %s", event_id, exc)
            return self.browse()
        with self.env.cr.savepoint():
            return self.sudo().create(
                {
                    "event_id": event_id,
                    "event_type": payload["event_type"],
                    "kartatap_company_id": order.kartatap_company_id,
                    "order_id": order.id,
                    "body": contract.serialize(payload),
                }
            )

    @api.model
    def _order_is_paid(self, order):
        """Evidence the customer actually paid: a settled online payment or a paid
        customer invoice. A confirmed order alone is not enough - an order can be
        confirmed by hand, or confirmed while its only payment attempt is still a
        draft, and neither may grant a paid plan."""
        if order.sudo().transaction_ids.filtered(lambda tx: tx.state == "done"):
            return True
        return bool(
            order.invoice_ids.filtered(
                lambda m: m.move_type == "out_invoice"
                and m.state == "posted"
                and m.payment_state in ("paid", "in_payment")
            )
        )

    @api.model
    def _reconcile(self, limit=RECONCILE_LIMIT):
        """Queue every event the current state of KartaTap orders implies."""
        orders = self.env["sale.order"].sudo().search(
            [
                ("kartatap_company_id", "!=", False),
                ("kartatap_request_id", "!=", False),
                ("state", "in", ("sale", "cancel")),
            ],
            order="id",
            limit=limit,
        )
        today = fields.Date.context_today(self)
        base = fields.Datetime.now()
        tick = [0]

        def clock():
            # Strictly increasing occurred_at within one scan, so the receiver's
            # "older than last applied" rule preserves the order events were queued.
            tick[0] += 1
            return base + timedelta(milliseconds=tick[0])

        created = self.browse()
        for order in orders:
            invoices = order.invoice_ids.filtered(
                lambda m: m.move_type == "out_invoice" and m.state == "posted"
            ).sorted("id")
            if order.state == "sale" and self._order_is_paid(order):
                start = order.date_order.date() if order.date_order else today
                created |= self._enqueue(order, "activated", clock(), period_end=self._period_end(order, start))
                # The first invoice bills the period the activation already granted.
                for invoice in invoices[1:]:
                    if invoice.payment_state in ("paid", "in_payment"):
                        created |= self._enqueue(
                            order,
                            "renewed",
                            clock(),
                            discriminator="inv%s" % invoice.id,
                            period_end=self._period_end(order, invoice.invoice_date or today),
                        )
                for invoice in invoices:
                    if (
                        invoice.payment_state in ("not_paid", "partial")
                        and invoice.invoice_date_due
                        and invoice.invoice_date_due < today
                    ):
                        created |= self._enqueue(
                            order, "past_due", clock(), discriminator="inv%s" % invoice.id
                        )
            ended = order.state == "cancel" or order.subscription_status == "c"
            if ended and self.sudo().search_count([("order_id", "=", order.id)]):
                # Only end what KartaTap was told had started.
                created |= self._enqueue(
                    order,
                    "canceled",
                    clock(),
                    reason_code="order_canceled" if order.state == "cancel" else "subscription_ended",
                )
        return created

    # ---------------------------------------------------------------- delivery

    @api.model
    def _claim_due(self, limit=DELIVERY_BATCH):
        """Lock the next deliverable event per tenant (earliest pending first)."""
        # Raw SQL below: pending ORM writes (a backoff just recorded) must reach
        # the database first or an event could be claimed before it is due.
        self.env.flush_all()
        self.env.cr.execute(
            """
            SELECT e.id
              FROM kartatap_entitlement_event e
             WHERE e.state = 'pending'
               AND e.next_attempt_at <= %s
               AND NOT EXISTS (
                     SELECT 1 FROM kartatap_entitlement_event p
                      WHERE p.kartatap_company_id = e.kartatap_company_id
                        AND p.state = 'pending'
                        AND p.id < e.id)
             ORDER BY e.id
             LIMIT %s
             FOR UPDATE SKIP LOCKED
            """,
            (fields.Datetime.now(), limit),
        )
        return self.browse([row[0] for row in self.env.cr.fetchall()])

    @staticmethod
    def _response_error_code(response):
        """The receiver's machine-readable `error` code, if any. Never the body."""
        try:
            code = response.json().get("error")
        except ValueError:
            return None
        return code if isinstance(code, str) and _ERROR_CODE.match(code) else None

    def _deliver(self, endpoint, secret):
        self.ensure_one()
        timestamp = int(time.time())
        status_code = None
        error = None
        try:
            response = requests.post(
                endpoint,
                data=self.body.encode("utf-8"),
                headers=contract.headers(secret, timestamp, self.body, self.event_id),
                timeout=HTTP_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            status_code = response.status_code
            code = self._response_error_code(response)
            error = "HTTP %s%s" % (status_code, " %s" % code if code else "")
        except requests.RequestException as exc:
            error = "network: %s" % type(exc).__name__

        outcome = contract.classify(status_code)
        now = fields.Datetime.now()
        attempts = self.attempts + 1
        vals = {"attempts": attempts, "last_status_code": status_code or 0}
        if outcome == "sent":
            vals.update({"state": "sent", "sent_at": now, "last_error": False})
        elif outcome == "reject":
            vals.update({"state": "rejected", "last_error": error})
            _logger.error("KartaTap refused entitlement event %s (%s); not retried.", self.event_id, error)
        elif attempts >= contract.MAX_ATTEMPTS:
            vals.update({"state": "dead", "last_error": error})
            _logger.error("KartaTap entitlement event %s dead-lettered after %s attempts (%s).", self.event_id, attempts, error)
        else:
            vals.update(
                {
                    "last_error": error,
                    "next_attempt_at": now + timedelta(seconds=contract.backoff_seconds(attempts)),
                }
            )
            _logger.warning("KartaTap entitlement event %s will retry (%s).", self.event_id, error)
        self.sudo().write(vals)
        return outcome

    @api.model
    def _deliver_due(self, limit=DELIVERY_BATCH):
        config = self._delivery_config()
        if not config:
            return 0
        endpoint, secret = config
        delivered = 0
        for event in self._claim_due(limit):
            if event._deliver(endpoint, secret) == "sent":
                delivered += 1
            self._commit()
        return delivered

    @api.model
    def _commit(self):
        # Commit per event so a crash mid-batch never re-sends what was delivered.
        # Tests run inside one rolled-back transaction and must not commit.
        if not modules.module.current_test:
            self.env.cr.commit()

    @api.model
    def _cron_process(self):
        if not self._push_enabled():
            return
        self._reconcile()
        self._commit()
        self._deliver_due()

    # ------------------------------------------------------------------ manual

    def action_retry(self):
        """Operator action: re-queue a rejected or dead-lettered event (same bytes)."""
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only a settings administrator may re-queue entitlement events."))
        for event in self:
            if event.state not in ("rejected", "dead"):
                raise UserError(_("Only rejected or dead-lettered events can be re-queued."))
        self.sudo().write(
            {"state": "pending", "attempts": 0, "next_attempt_at": fields.Datetime.now()}
        )
        return True

    def payload(self):
        """Parsed body, for inspection."""
        self.ensure_one()
        return json.loads(self.body)
