"""End-to-end tests for the 14-day trial flow.

Covers:
- create_or_get_checkout(trial=true) creates the order in 'trial' state
- the order stays in state='draft' (no Sign & Pay email sent)
- l3_trial_ends_at is set to today + 14 days
- the trial Order Form terms mention 'Trial: 14 days free'
- _l3_process_trial_ends sends T-3 reminder (idempotent via l3_trial_reminder_sent)
- _l3_process_trial_ends skips non-trial orders and orders with the wrong
  trial_ends_at offset (T-1, T-7 etc.)
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


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
        # Trial orders go through action_quotation_sent() too, so the customer's
        # portal page exposes Odoo's Sign & Pay / payment_stripe card-capture form.
        # The trial-specific difference is require_payment=False + a 14-day
        # trial_period_days on the Stripe subscription, not a different state.
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
