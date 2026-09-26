import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..lib import entitlement_contract as contract

POST = "odoo.addons.sgc_kartatap_bridge.models.kartatap_entitlement_event.requests.post"
PAID = "odoo.addons.sgc_kartatap_bridge.models.kartatap_entitlement_event.KartatapEntitlementEvent._order_is_paid"
SECRET = "test-secret-0123456789abcdef0123456789abcdef"


def _response(status, error=None):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = {"error": error} if error else {"ok": True}
    return response


@tagged("post_install", "-at_install", "kartatap_bridge")
class TestEntitlementOutbox(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].sudo().create(
            {"name": "KartaTap", "currency_id": cls.env.ref("base.AED").id}
        )
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_kartatap_bridge.company_id", str(cls.company.id))
        ICP.set_param("sgc_kartatap_bridge.checkout_enabled", "True")
        ICP.set_param("sgc_kartatap_bridge.entitlement_push_enabled", "True")
        ICP.set_param("sgc_kartatap_bridge.entitlement_signing_secret", SECRET)

        Period = cls.env["product.subscription.period"].sudo()
        cls.monthly = Period.search([("unit", "=", "month"), ("duration", "=", 1)], limit=1) or Period.create(
            {"name": "1 Month", "unit": "month", "duration": 1}
        )
        cls.yearly = Period.search([("unit", "=", "year"), ("duration", "=", 1)], limit=1) or Period.create(
            {"name": "1 Year", "unit": "year", "duration": 1}
        )
        cls.team = cls.env["product.product"].sudo().create(
            {
                "name": "KartaTap TEAM",
                "default_code": "KT-TEAM",
                "type": "service",
                "is_recurring": True,
                "list_price": 22.0,
                "company_id": cls.company.id,
            }
        )
        cls.Checkout = cls.env["kartatap.checkout"].sudo()
        cls.Event = cls.env["kartatap.entitlement.event"].sudo()

    def _order(self, tenant="tenant-alpha-01", request_id="req-outbox-0001", **extra):
        payload = {
            "kartatap_company_id": tenant,
            "kartatap_request_id": request_id,
            "plan_code": "TEAM",
            "quantity": 3,
            "currency": "AED",
            "company_name": "Tenant %s" % tenant,
        }
        payload.update(extra)
        result = self.Checkout.create_or_get_kartatap_checkout(payload)
        return self.env["sale.order"].sudo().browse(result["odoo"]["sale_order_id"])

    def setUp(self):
        super().setUp()
        # Most tests exercise delivery, not payment detection: treat confirmed
        # orders as paid unless a test says otherwise.
        self.paid = patch(PAID, return_value=True)
        self.paid.start()
        self.addCleanup(patch.stopall)

    def _confirmed(self, **kwargs):
        order = self._order(**kwargs)
        order.action_confirm()
        return order

    # --------------------------------------------------------------- checkout

    def test_checkout_accepts_billing_interval_and_display_currency(self):
        order = self._order(request_id="req-interval-01", billing_interval="month", currency="USD")
        self.assertEqual(order.recurrance_id, self.monthly)
        self.assertEqual(order.currency_id, self.company.currency_id)

    def test_checkout_rejects_unknown_interval_and_malformed_currency(self):
        with self.assertRaises(ValidationError):
            self._order(request_id="req-interval-02", billing_interval="weekly")
        with self.assertRaises(ValidationError):
            self._order(request_id="req-interval-03", currency="usd1")

    def test_yearly_checkout_requires_an_explicit_yearly_price(self):
        with self.assertRaises(UserError):
            self._order(request_id="req-yearly-01", billing_interval="year")

    # -------------------------------------------------------------- reconcile

    def test_confirmed_order_queues_one_activation(self):
        order = self._confirmed()
        created = self.Event._reconcile()
        self.assertEqual(len(created), 1)
        body = json.loads(created.body)
        self.assertEqual(body["event_type"], "subscription.activated")
        self.assertEqual(body["status"], "active")
        self.assertEqual(body["kartatap_company_id"], "tenant-alpha-01")
        self.assertEqual(body["plan_code"], "TEAM")
        self.assertEqual(body["quantity"], 3)
        self.assertEqual(body["odoo_subscription_ref"], "sale.order:%s" % order.id)
        self.assertTrue(body["effective_period_end"])
        # Idempotent: a second scan queues nothing new.
        self.assertFalse(self.Event._reconcile())

    def test_confirmed_but_unpaid_order_queues_nothing(self):
        self.paid.stop()
        order = self._confirmed(request_id="req-unpaid-01")
        self.assertFalse(self.Event._order_is_paid(order))
        self.assertFalse(self.Event._reconcile())

    def test_quotation_queues_nothing(self):
        self._order(request_id="req-quote-only")
        self.assertFalse(self.Event._reconcile())

    def test_cancellation_follows_an_activation_only(self):
        order = self._confirmed(request_id="req-cancel-01")
        self.Event._reconcile()
        order.subscription_status = "c"
        created = self.Event._reconcile()
        self.assertEqual(created.mapped("event_type"), ["subscription.canceled"])
        self.assertEqual(json.loads(created.body)["reason_code"], "subscription_ended")

    # --------------------------------------------------------------- delivery

    def _queued(self, **kwargs):
        self._confirmed(**kwargs)
        return self.Event._reconcile()

    def test_delivery_success_marks_sent_and_signs_the_frozen_body(self):
        event = self._queued(request_id="req-deliver-01")
        with patch(POST, return_value=_response(200)) as post:
            self.assertEqual(self.Event._deliver_due(), 1)
        self.assertEqual(event.state, "sent")
        args, kwargs = post.call_args
        self.assertEqual(kwargs["data"], event.body.encode("utf-8"))
        self.assertFalse(kwargs["allow_redirects"])
        headers = kwargs["headers"]
        expected = contract.sign(SECRET, headers["x-kartatap-timestamp"], event.body)
        self.assertEqual(headers["x-kartatap-signature"], "v1=%s" % expected)

    def test_transient_failure_backs_off(self):
        event = self._queued(request_id="req-deliver-02")
        with patch(POST, return_value=_response(503, "odoo_entitlement_sync_disabled")):
            self.Event._deliver_due()
        self.assertEqual(event.state, "pending")
        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.last_error, "HTTP 503 odoo_entitlement_sync_disabled")
        self.assertGreater(event.next_attempt_at, fields.Datetime.now() + timedelta(seconds=30))
        # Not due yet: nothing is sent on the next run.
        with patch(POST) as post:
            self.assertEqual(self.Event._deliver_due(), 0)
            post.assert_not_called()

    def test_network_fault_is_retried(self):
        event = self._queued(request_id="req-deliver-03")
        with patch(POST, side_effect=requests.ConnectionError("down")):
            self.Event._deliver_due()
        self.assertEqual(event.state, "pending")
        self.assertEqual(event.last_error, "network: ConnectionError")

    def test_refusal_is_final(self):
        event = self._queued(request_id="req-deliver-04")
        with patch(POST, return_value=_response(401, "invalid_signature")):
            self.Event._deliver_due()
        self.assertEqual(event.state, "rejected")

    def test_dead_letter_after_max_attempts(self):
        event = self._queued(request_id="req-deliver-05")
        event.write({"attempts": contract.MAX_ATTEMPTS - 1})
        with patch(POST, return_value=_response(502)):
            self.Event._deliver_due()
        self.assertEqual(event.state, "dead")

    def test_events_for_one_tenant_are_delivered_in_order(self):
        order = self._confirmed(request_id="req-order-01")
        first = self.Event._reconcile()
        order.subscription_status = "c"
        second = self.Event._reconcile()
        with patch(POST, return_value=_response(503)):
            self.Event._deliver_due()
        self.assertEqual(first.attempts, 1)
        self.assertEqual(second.attempts, 0, "a later event must wait for the earlier one")

    def test_nothing_happens_when_push_is_disabled_or_unconfigured(self):
        self._confirmed(request_id="req-off-01")
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_kartatap_bridge.entitlement_push_enabled", "False")
        with patch(POST) as post:
            self.Event._cron_process()
            post.assert_not_called()
        self.assertFalse(self.Event.search([]))

        ICP.set_param("sgc_kartatap_bridge.entitlement_push_enabled", "True")
        ICP.set_param("sgc_kartatap_bridge.entitlement_signing_secret", "too-short")
        with patch(POST) as post:
            self.Event._cron_process()
            post.assert_not_called()

    def test_operator_can_requeue_a_rejected_event(self):
        event = self._queued(request_id="req-requeue-01")
        with patch(POST, return_value=_response(400, "malformed_json")):
            self.Event._deliver_due()
        event.with_user(self.env.ref("base.user_admin")).action_retry()
        self.assertEqual((event.state, event.attempts), ("pending", 0))
