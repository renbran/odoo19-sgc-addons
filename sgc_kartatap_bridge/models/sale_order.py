import hashlib
import hmac
import json
import logging
import time
import uuid

import requests

from odoo import fields, models

_logger = logging.getLogger(__name__)

_ENTITLEMENT_TIMEOUT_S = 10


class SaleOrder(models.Model):
    """Additive fields + the outbound entitlement-event sender for the
    KartaTap billing integration (sgc_kartatap_bridge).
    """

    _inherit = "sale.order"

    kartatap_request_id = fields.Char(
        string="KartaTap Request Id",
        index=True,
        help="The kt-<companyId>-<hash> idempotency key KartaTap sent when "
        "creating this checkout. Never set for orders created outside the "
        "KartaTap integration.",
    )
    kartatap_company_id = fields.Char(
        string="KartaTap Company Id",
        index=True,
        help="KartaTap's own Company.id (Prisma cuid) for the tenant this "
        "order belongs to.",
    )
    kartatap_event_sent = fields.Boolean(
        string="KartaTap Entitlement Event Sent",
        default=False,
        help="True once a subscription.activated entitlement event has been "
        "POSTed to KartaTap for this order's payment. Prevents duplicate "
        "sends if _post_process runs more than once for the same "
        "transaction.",
    )

    _sql_constraints = [
        (
            "kartatap_request_id_unique",
            "unique(kartatap_request_id)",
            "A KartaTap checkout request id must map to exactly one order.",
        ),
    ]

    def _kartatap_plan_code(self):
        """Derive SOLO/TEAM/BUSINESS from the order's single KartaTap
        product line. Only ever called on orders that already carry
        kartatap_request_id.
        """
        self.ensure_one()
        for line in self.order_line:
            name = (line.product_id.name or "").strip()
            if name.upper().startswith("KARTATAP "):
                return name.split(" ", 1)[1].strip().upper()
        return None

    def _send_kartatap_entitlement_event(self, event_type, status):
        """POST one signed entitlement event to KartaTap, matching the
        HMAC-SHA256 v1=<hex> contract in kartatap's
        src/lib/odoo-billing/entitlements.ts (signature over
        "<timestamp>.<raw body bytes>"). Best-effort, single attempt: this
        module intentionally does not implement retry/dead-letter (that is
        KartaTap-side, and per F40 not wired to a consumer yet either) --
        a failure here is logged, not raised, so it never blocks or
        rolls back the underlying payment.
        """
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        url = icp.get_param("kartatap.entitlement_url")
        secret = icp.get_param("kartatap.entitlement_signing_secret")
        if not url or not secret:
            _logger.warning(
                "sgc_kartatap_bridge: entitlement sender not configured "
                "(kartatap.entitlement_url / kartatap.entitlement_signing_secret "
                "missing); skipping event for order %s",
                self.name,
            )
            return False

        plan_code = self._kartatap_plan_code()
        if not plan_code or not self.kartatap_company_id:
            _logger.warning(
                "sgc_kartatap_bridge: order %s is not a KartaTap checkout "
                "order (missing plan/company); skipping entitlement event",
                self.name,
            )
            return False

        quantity = int(sum(self.order_line.mapped("product_uom_qty"))) or 1
        event_id = f"evt-{self.id}-{uuid.uuid4().hex[:12]}"
        body = {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": fields.Datetime.to_string(fields.Datetime.now()).replace(" ", "T") + "Z",
            "source": "odoo",
            "schema_version": 1,
            "kartatap_company_id": self.kartatap_company_id,
            "plan_code": plan_code,
            "quantity": quantity,
            "status": status,
            "odoo_partner_ref": str(self.partner_id.id),
            "odoo_subscription_ref": self.name,
            "effective_period_end": None,
            "reason_code": None,
        }
        raw_body = json.dumps(body, separators=(",", ":"), sort_keys=True)
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}.{raw_body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "content-type": "application/json",
            "x-kartatap-timestamp": timestamp,
            "x-kartatap-signature": f"v1={signature}",
            "x-kartatap-event-id": event_id,
        }

        try:
            response = requests.post(
                url,
                data=raw_body.encode("utf-8"),
                headers=headers,
                timeout=_ENTITLEMENT_TIMEOUT_S,
            )
        except requests.RequestException as exc:
            _logger.error(
                "sgc_kartatap_bridge: entitlement POST failed for order %s: %s",
                self.name,
                exc,
            )
            return False

        if response.status_code == 200:
            self.kartatap_event_sent = True
            _logger.info(
                "sgc_kartatap_bridge: entitlement event %s sent for order %s (%s)",
                event_id,
                self.name,
                response.status_code,
            )
            return True

        _logger.error(
            "sgc_kartatap_bridge: entitlement event %s rejected for order %s: "
            "HTTP %s %s",
            event_id,
            self.name,
            response.status_code,
            response.text[:200],
        )
        return False
