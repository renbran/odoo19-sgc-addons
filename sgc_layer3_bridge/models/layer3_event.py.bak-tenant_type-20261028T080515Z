import json
import logging
import time
from datetime import timedelta

import requests

from odoo import _, api, fields, models, modules
from odoo.exceptions import UserError

from ..lib import contract

_logger = logging.getLogger(__name__)

PARAM_PREFIX = "sgc_layer3_bridge."
HTTP_TIMEOUT_SECONDS = 8
DELIVERY_BATCH = 20


class Layer3Event(models.Model):
    """Durable outbox of signed ``tenant.sync`` snapshots for the tenant receiver.

    Written first, delivered by the cron, so a receiver outage never loses a change.
    Delivery is at-least-once and strictly in order per tenant; the receiver ignores a
    snapshot whose ``version`` is not newer than the one it applied.
    """

    _name = "layer3.event"
    _description = "Layer 3 tenant sync event (outbox)"
    _order = "id desc"
    _rec_name = "event_id"

    event_id = fields.Char(required=True, index=True, readonly=True, copy=False)
    tenant_slug = fields.Char(required=True, index=True, readonly=True)
    order_id = fields.Many2one("sale.order", ondelete="set null", index=True, readonly=True)
    tenant_state = fields.Char(readonly=True)
    provision = fields.Boolean(readonly=True)
    body = fields.Text(required=True, readonly=True, help="Exact JSON bytes that are signed and sent.")
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Delivered"), ("rejected", "Rejected"), ("dead", "Dead-lettered")],
        default="pending",
        required=True,
        index=True,
    )
    attempts = fields.Integer(default=0, readonly=True)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    last_status_code = fields.Integer(readonly=True)
    last_error = fields.Char(readonly=True)
    sent_at = fields.Datetime(readonly=True)

    _event_id_uniq = models.Constraint("unique(event_id)", "A Layer 3 event with this id already exists.")

    @api.model
    def _param(self, key, default=None):
        return self.env["ir.config_parameter"].sudo().get_param(PARAM_PREFIX + key, default)

    @api.model
    def _push_enabled(self):
        return str(self._param("push_enabled", "False")).strip().lower() in ("true", "1", "yes")

    @api.model
    def _delivery_config(self):
        endpoint = (self._param("receiver_endpoint") or "").strip()
        if not endpoint.startswith("https://") or "@" in endpoint.split("/")[2]:
            _logger.error("Layer 3 push: the receiver endpoint must be an https URL without credentials.")
            return None
        secret = (self._param("signing_secret") or "").strip()
        if len(secret) < contract.MIN_SECRET_LENGTH:
            _logger.error("Layer 3 push: %ssigning_secret is missing or too short.", PARAM_PREFIX)
            return None
        return endpoint, secret

    # ------------------------------------------------------------------ enqueue

    @api.model
    def _billing_url(self, order):
        base = (self._param("public_base_url") or "").strip().rstrip("/") or (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url", "").rstrip("/")
        )
        if not base.startswith("https://"):
            return None
        order._portal_ensure_token()
        return "%s/my/layer3/%s?access_token=%s" % (base, order.id, order.access_token)

    @api.model
    def _enqueue(self, order, provision=False):
        db_uuid = (self.env["ir.config_parameter"].sudo().get_param("database.uuid") or "db")[:8]
        event_id = "odoo:%s:so%s:v%s" % (db_uuid, order.id, order.l3_state_version)
        if self.sudo().search_count([("event_id", "=", event_id)]):
            return self.browse()
        try:
            payload = contract.build_payload(
                event_id=event_id,
                occurred_at=fields.Datetime.now(),
                tenant_slug=order.l3_tenant_slug,
                version=order.l3_state_version,
                state=order.l3_state,
                reason=order.l3_state_reason or "paid",
                docs_status=order.l3_docs_status or "pending",
                users=order.l3_users or 5,
                order_ref="sale.order/%s" % order.id,
                company_name=order.partner_id.commercial_partner_id.name,
                billing_url=self._billing_url(order),
                licence_expiry=order.l3_licence_expiry,
                provision=provision,
                admin_email=order.l3_admin_email,
                admin_name=order.l3_admin_name,
            )
        except contract.ContractError as exc:
            _logger.error("Layer 3 event %s not queued: %s", event_id, exc)
            order.message_post(body=_("Layer 3 sync event not queued: %s") % exc)
            return self.browse()
        return self.sudo().create(
            {
                "event_id": event_id,
                "tenant_slug": order.l3_tenant_slug,
                "order_id": order.id,
                "tenant_state": order.l3_state,
                "provision": provision,
                "body": contract.serialize(payload),
            }
        )

    # ---------------------------------------------------------------- delivery

    @api.model
    def _claim_due(self, limit=DELIVERY_BATCH):
        self.env.flush_all()
        self.env.cr.execute(
            """
            SELECT e.id
              FROM layer3_event e
             WHERE e.state = 'pending'
               AND e.next_attempt_at <= %s
               AND NOT EXISTS (
                     SELECT 1 FROM layer3_event p
                      WHERE p.tenant_slug = e.tenant_slug
                        AND p.state = 'pending'
                        AND p.id < e.id)
             ORDER BY e.id
             LIMIT %s
             FOR UPDATE SKIP LOCKED
            """,
            (fields.Datetime.now(), limit),
        )
        return self.browse([row[0] for row in self.env.cr.fetchall()])

    def _deliver(self, endpoint, secret):
        self.ensure_one()
        timestamp = int(time.time())
        status_code = None
        try:
            response = requests.post(
                endpoint,
                data=self.body.encode("utf-8"),
                headers=contract.headers(secret, timestamp, self.body, self.event_id),
                timeout=HTTP_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            status_code = response.status_code
            error = "HTTP %s" % status_code
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
            _logger.error("Tenant receiver refused Layer 3 event %s (%s).", self.event_id, error)
        elif attempts >= contract.MAX_ATTEMPTS:
            vals.update({"state": "dead", "last_error": error})
            _logger.error("Layer 3 event %s dead-lettered after %s attempts (%s).", self.event_id, attempts, error)
        else:
            vals.update({"last_error": error, "next_attempt_at": now + timedelta(seconds=contract.backoff_seconds(attempts))})
        self.sudo().write(vals)
        return outcome

    @api.model
    def _deliver_due(self, limit=DELIVERY_BATCH):
        config = self._delivery_config()
        if not config:
            return 0
        delivered = 0
        for event in self._claim_due(limit):
            if event._deliver(*config) == "sent":
                delivered += 1
            self._commit()
        return delivered

    @api.model
    def _commit(self):
        # Commit per step so a crash never re-sends what was delivered. Tests must not commit.
        if not modules.module.current_test:
            self.env.cr.commit()

    @api.model
    def _cron_process(self):
        self.env["sale.order"]._l3_cron()
        self._commit()
        if self._push_enabled():
            self._deliver_due()

    def action_retry(self):
        if not self.env.user.has_group("base.group_system"):
            raise UserError(_("Only a settings administrator may re-queue Layer 3 events."))
        if self.filtered(lambda e: e.state not in ("rejected", "dead")):
            raise UserError(_("Only rejected or dead-lettered events can be re-queued."))
        self.sudo().write({"state": "pending", "attempts": 0, "next_attempt_at": fields.Datetime.now()})
        return True

    def payload(self):
        self.ensure_one()
        return json.loads(self.body)
