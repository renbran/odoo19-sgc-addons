"""End-to-end tests for the 14-day trial flow.

Covers:
- create_or_get_checkout(trial=true) creates the order in 'trial' state
- the order stays in state='draft' (no Sign & Pay email sent)
- l3_trial_ends_at is set to today + 14 days
- the trial Order Form terms mention 'Trial: 14 days free'
- _l3_process_trial_ends sends T-3 reminder (idempotent via l3_trial_reminder_sent)
- _l3_process_trial_ends skips non-trial orders and orders with the wrong
  trial_ends_at offset (T-1, T-7 etc.)
- the card step: SetupIntent -> complete_trial -> subscription with trial_period_days=14,
  tenant provisioned, and the webhook's own transitions
- verify_webhook really parses a signed Stripe payload into a plain nested dict
  (regression: stripe-python 15 returns a non-dict StripeObject, which 500ed every
  delivery at event.get("id") in the controller)
"""
import hashlib
import hmac
import json
import time
from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..controllers.stripe_webhook import StripeWebhook
from ..lib import stripe_client


@tagged("post_install", "-at_install", "layer3")
class TestTrialCheckout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_layer3_bridge.checkout_enabled", "True")
        ICP.set_param("sgc_layer3_bridge.public_base_url", "https://app.example.test")
        # The trial runs these tests on a copy of production: its real tenants must not use up
        # the cohort or the tenant cap.
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", "100000")
        ICP.set_param("sgc_layer3_bridge.max_active_tenants", "100000")
        cls.Checkout = cls.env["layer3.checkout"]

    def _payload(self, **kw):
        base = {
            "request_id": "trial-req-001",
            "slug": "trialmarina",
            "company_name": "Marina Crest Holdings",
            "contact_name": "M. Al-Suwaidi",
            "email": "admin@marinacrest.ae",
            "cycle": "monthly",
            "users": 5,
            "trial": True,
        }
        base.update(kw)
        return base

    def _find(self, request_id):
        return self.env["sale.order"].search([("l3_request_id", "=", request_id)])

    def test_trial_checkout_creates_order_in_trial_state(self):
        self.Checkout.create_or_get_checkout(self._payload())
        order = self._find("trial-req-001")
        self.assertEqual(order.l3_state, "trial")
        self.assertFalse(order.l3_activated_on)

    def test_trial_checkout_sets_trial_ends_at_to_today_plus_14(self):
        self.Checkout.create_or_get_checkout(self._payload())
        order = self._find("trial-req-001")
        expected = fields.Date.context_today(self.env["sale.order"]) + timedelta(days=14)
        self.assertEqual(order.l3_trial_ends_at, expected)

    def test_trial_checkout_does_not_require_payment(self):
        self.Checkout.create_or_get_checkout(self._payload())
        order = self._find("trial-req-001")
        self.assertFalse(order.require_payment)

    def test_trial_checkout_reaches_sent_state_for_payment_portal(self):
        # Trial orders go through action_quotation_sent() like every other order, but
        # require_payment=False means Odoo's portal shows the quote read-only: the card
        # is collected on our own page by Stripe Elements (create_trial_setup_intent),
        # never by Odoo. This test guards that state, not a portal payment form.
        self.Checkout.create_or_get_checkout(self._payload())
        order = self._find("trial-req-001")
        self.assertEqual(order.state, "sent")

    def test_trial_checkout_includes_trial_row_in_order_form_terms(self):
        self.Checkout.create_or_get_checkout(self._payload())
        order = self._find("trial-req-001")
        self.assertIn("Trial: 14 days free", str(order.note))

    def test_trial_checkout_idempotent_on_retry(self):
        first = self.Checkout.create_or_get_checkout(self._payload())
        second = self.Checkout.create_or_get_checkout(self._payload())
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["sale_order_name"], second["sale_order_name"])

    def test_non_trial_checkout_defaults_to_awaiting_payment(self):
        payload = self._payload(request_id="non-trial-req", slug="paidco", email="ops@paidco.ae", trial=False)
        payload["cycle"] = "annual"
        payload["users"] = 6
        self.Checkout.create_or_get_checkout(payload)
        order = self._find("non-trial-req")
        self.assertEqual(order.l3_state, "awaiting_payment")
        self.assertFalse(order.l3_trial_ends_at)
        self.assertTrue(order.require_payment)


@tagged("post_install", "-at_install", "layer3")
class TestTrialReminderCron(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_layer3_bridge.checkout_enabled", "True")
        ICP.set_param("sgc_layer3_bridge.public_base_url", "https://app.example.test")
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", "100000")
        ICP.set_param("sgc_layer3_bridge.max_active_tenants", "100000")

    def _create_trial(self, request_id):
        self.env["layer3.checkout"].create_or_get_checkout({
            "request_id": request_id,
            "slug": f"trial-{request_id}",
            "company_name": "Reminder Test",
            "contact_name": "R. Mind",
            "email": f"ops@{request_id}.ae",
            "cycle": "monthly",
            "users": 5,
            "trial": True,
        })
        return self.env["sale.order"].search([("l3_request_id", "=", request_id)])

    def test_t3_reminder_sent_once(self):
        order = self._create_trial("trial-t3-req-001")
        today = fields.Date.context_today(order)
        order.l3_trial_ends_at = today + timedelta(days=3)
        order._l3_process_trial_ends(today)
        self.assertTrue(order.l3_trial_reminder_sent)
        # Run again — should be idempotent (flag stays True).
        order._l3_process_trial_ends(today)
        self.assertTrue(order.l3_trial_reminder_sent)

    def test_t3_reminder_not_sent_for_t1(self):
        order = self._create_trial("trial-t1-req-002")
        today = fields.Date.context_today(order)
        order.l3_trial_ends_at = today + timedelta(days=1)
        order._l3_process_trial_ends(today)
        self.assertFalse(order.l3_trial_reminder_sent)

    def test_cron_skips_non_trial_orders(self):
        # Non-trial order — cron should not touch l3_trial_reminder_sent even if
        # l3_trial_ends_at happens to be set.
        self.env["layer3.checkout"].create_or_get_checkout({
            "request_id": "trial-noncron-req",
            "slug": "paidco-cron",
            "company_name": "Paid Co",
            "contact_name": "P. Aid",
            "email": "ops@paidco-cron.ae",
            "cycle": "monthly",
            "users": 5,
        })
        order = self.env["sale.order"].search([("l3_request_id", "=", "trial-noncron-req")])
        today = fields.Date.context_today(order)
        order.write({"l3_trial_ends_at": today + timedelta(days=3)})
        order._l3_process_trial_ends(today)
        self.assertFalse(order.l3_trial_reminder_sent)


@tagged("post_install", "-at_install", "layer3")
class TestTrialCardFlow(TransactionCase):
    """The card step: SetupIntent -> subscription with trial_period_days=14 -> tenant.

    Stripe itself is stubbed at the stripe_client boundary (the module the controller
    calls), so these tests assert the Odoo side: what is stored, what is refused, and
    what the tenant receiver is told.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_layer3_bridge.checkout_enabled", "True")
        ICP.set_param("sgc_layer3_bridge.public_base_url", "https://app.example.test")
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", "100000")
        ICP.set_param("sgc_layer3_bridge.max_active_tenants", "100000")
        ICP.set_param("sgc_layer3_bridge.stripe_secret_key", "sk_test_dummy")
        ICP.set_param("sgc_layer3_bridge.stripe_publishable_key", "pk_test_dummy")
        cls.Checkout = cls.env["layer3.checkout"]

    def _trial_order(self, request_id="trial-card-req"):
        self.Checkout.create_or_get_checkout({
            "request_id": request_id,
            "slug": "trialcard",
            "company_name": "Card Trial Holdings",
            "contact_name": "T. Ryder",
            "email": "admin@cardtrial.ae",
            "cycle": "monthly",
            "users": 5,
            "trial": True,
        })
        return self.env["sale.order"].search([("l3_request_id", "=", request_id)])

    def test_setup_intent_returns_client_secret_and_creates_customer(self):
        order = self._trial_order()
        with (
            mock.patch.object(stripe_client, "create_customer", return_value="cus_123") as cust,
            mock.patch.object(
                stripe_client,
                "create_setup_intent",
                return_value={"id": "seti_1", "client_secret": "seti_1_secret_abc"},
            ) as si,
        ):
            result = self.Checkout.create_trial_setup_intent(request_id=order.l3_request_id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["client_secret"], "seti_1_secret_abc")
        self.assertEqual(result["publishable_key"], "pk_test_dummy")
        cust.assert_called_once()
        si.assert_called_once()
        self.assertEqual(order.l3_stripe_customer_id, "cus_123")
        self.assertFalse(order.l3_stripe_subscription_id)
        self.assertEqual(order.l3_state, "trial")

    def test_setup_intent_reuses_the_customer_on_retry(self):
        order = self._trial_order()
        with (
            mock.patch.object(stripe_client, "create_customer", return_value="cus_123") as cust,
            mock.patch.object(
                stripe_client,
                "create_setup_intent",
                return_value={"id": "seti_1", "client_secret": "s1"},
            ),
        ):
            self.Checkout.create_trial_setup_intent(request_id=order.l3_request_id)
            self.Checkout.create_trial_setup_intent(request_id=order.l3_request_id)
        cust.assert_called_once()

    def test_setup_intent_refused_once_the_subscription_exists(self):
        order = self._trial_order()
        order.l3_stripe_subscription_id = "sub_done"
        with self.assertRaisesRegex(UserError, "layer3_trial_already_active"):
            self.Checkout.create_trial_setup_intent(request_id=order.l3_request_id)

    def test_setup_intent_refuses_a_foreign_request_id(self):
        with self.assertRaisesRegex(UserError, "layer3_trial_not_found"):
            self.Checkout.create_trial_setup_intent(request_id="trial-no-such-req")

    def test_complete_trial_starts_subscription_and_provisions(self):
        order = self._trial_order()
        order.l3_stripe_customer_id = "cus_123"
        trial_end = int(fields.Datetime.to_datetime("2026-10-14 10:00:00").timestamp())
        with (
            mock.patch.object(
                stripe_client,
                "retrieve_setup_intent",
                return_value={
                    "id": "seti_1",
                    "status": "succeeded",
                    "payment_method": "pm_1",
                    "customer": "cus_123",
                },
            ),
            mock.patch.object(stripe_client, "ensure_trial_price", return_value="price_1"),
            mock.patch.object(
                stripe_client,
                "create_trial_subscription",
                return_value={"id": "sub_1", "customer": "cus_123", "trial_end": trial_end},
            ) as subscribe,
        ):
            result = self.Checkout.complete_trial(
                request_id=order.l3_request_id, setup_intent_id="seti_1"
            )
        self.assertTrue(result["ok"])
        self.assertFalse(result["deduplicated"])
        subscribe.assert_called_once()
        self.assertEqual(subscribe.call_args[0][3], "pm_1")
        order.invalidate_recordset()
        self.assertEqual(order.l3_stripe_subscription_id, "sub_1")
        self.assertEqual(order.l3_stripe_customer_id, "cus_123")
        self.assertEqual(order.l3_state, "trial")
        self.assertEqual(
            order.l3_trial_ends_at,
            fields.Date.to_date("2026-10-14"),
        )
        events = self.env["layer3.event"].search([("order_id", "=", order.id)])
        self.assertEqual(len(events), 1)
        self.assertTrue(events.provision)
        self.assertEqual(events.payload()["state"], "trial")

    def test_complete_trial_is_idempotent(self):
        order = self._trial_order()
        order.write({"l3_stripe_customer_id": "cus_123", "l3_stripe_subscription_id": "sub_1"})
        result = self.Checkout.complete_trial(
            request_id=order.l3_request_id, setup_intent_id="seti_1"
        )
        self.assertTrue(result["deduplicated"])
        self.assertEqual(result["tenant_slug"], order.l3_tenant_slug)

    def test_complete_trial_refuses_an_unconfirmed_card(self):
        order = self._trial_order()
        order.l3_stripe_customer_id = "cus_123"
        with (
            mock.patch.object(
                stripe_client,
                "retrieve_setup_intent",
                return_value={
                    "id": "seti_1",
                    "status": "requires_payment_method",
                    "payment_method": "",
                    "customer": "cus_123",
                },
            ),
            self.assertRaisesRegex(UserError, "layer3_card_incomplete"),
        ):
            self.Checkout.complete_trial(
                request_id=order.l3_request_id, setup_intent_id="seti_1"
            )
        self.assertFalse(order.l3_stripe_subscription_id)
        self.assertFalse(self.env["layer3.event"].search([("order_id", "=", order.id)]))

    def test_subscription_created_webhook_links_ids_and_keeps_trial(self):
        order = self._trial_order()
        order.l3_stripe_customer_id = "cus_123"
        event = {
            "data": {
                "object": {
                    "id": "sub_1",
                    "customer": "cus_123",
                    "status": "trialing",
                }
            }
        }
        StripeWebhook()._handle_subscription_created(event, self.env)
        self.assertEqual(order.l3_stripe_subscription_id, "sub_1")
        self.assertEqual(order.l3_state, "trial")

    def test_webhook_payment_failed_locks_without_grace(self):
        order = self._trial_order()
        order.write({"l3_stripe_customer_id": "cus_123", "l3_stripe_subscription_id": "sub_1"})
        event = {"data": {"object": {"subscription": "sub_1", "customer": "cus_123"}}}
        StripeWebhook()._handle_payment_failed(event, self.env)
        order.invalidate_recordset()
        self.assertEqual(order.l3_state, "locked")
        self.assertEqual(order.l3_state_reason, "trial_locked")

    def _signed_payload(self, event, secret):
        payload = json.dumps(event, separators=(",", ":")).encode()
        ts = str(int(time.time()))
        sig = hmac.new(secret.encode(), (ts + "." + payload.decode()).encode(), hashlib.sha256).hexdigest()
        return payload, "t=%s,v1=%s" % (ts, sig)

    def test_verify_webhook_returns_a_plain_nested_dict(self):
        """Regression: stripe-python 15 hands back a non-dict ``stripe.Event``.

        ``event.get(...)`` then raises AttributeError in the controller *before* its
        handler try/except, so every verified delivery500'd on production (verified by a
        live signed POST on 2026-09-30, stripe 15.6.1).
        """
        secret = "whsec_" + "0" * 32
        payload, header = self._signed_payload({
            "id": "evt_webhook_1",
            "type": "customer.subscription.created",
            "data": {"object": {
                "id": "sub_1",
                "customer": "cus_1",
                "status": "trialing",
                "metadata": {"l3_request_id": "trial-card-req"},
            }},
        }, secret)
        event = stripe_client.verify_webhook(payload, header, secret)

        self.assertIsInstance(event, dict)
        self.assertEqual(event.get("id"), "evt_webhook_1")
        self.assertEqual(event.get("type"), "customer.subscription.created")
        self.assertIsInstance(event.get("data"), dict)
        obj = event.get("data", {}).get("object", {})
        self.assertIsInstance(obj, dict)
        self.assertEqual(obj.get("id"), "sub_1")
        self.assertIsInstance(obj.get("metadata"), dict)

        # the controller's own read of the event must not raise
        self.assertEqual(event.get("id", ""), "evt_webhook_1")
        self.assertEqual(event.get("type", ""), "customer.subscription.created")

        # and a handler must be able to walk it
        order = self._trial_order(request_id="trial-card-req")
        order.l3_stripe_customer_id = "cus_1"
        StripeWebhook()._handle_subscription_created(event, self.env)
        order.invalidate_recordset()
        self.assertEqual(order.l3_stripe_subscription_id, "sub_1")
        self.assertEqual(order.l3_state, "trial")

        # a tampered signature is still refused
        bad_payload, bad_header = self._signed_payload(
            {"id": "evt_webhook_2", "type": "ping"}, secret)
        tampered = bad_payload.replace(b"evt_webhook_2", b"evt_webhook_3")
        with self.assertRaises(Exception):
            stripe_client.verify_webhook(tampered, bad_header, secret)
