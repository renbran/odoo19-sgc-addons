from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "layer3")
class TestCheckout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_layer3_bridge.checkout_enabled", "True")
        ICP.set_param("sgc_layer3_bridge.public_base_url", "https://app.example.test")
        # The trial runs these tests on a copy of production: its real tenants must not use up
        # the cohort or the tenant cap. Tests that need a full cohort set it themselves.
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", "100000")
        ICP.set_param("sgc_layer3_bridge.max_active_tenants", "100000")
        cls.Checkout = cls.env["layer3.checkout"]

    def test_annual_order_prices_and_terms(self):
        result = self.Checkout.create_or_get_checkout(self._payload())
        order = self.env["sale.order"].search([("l3_request_id", "=", "req-0001-marinacrest")])
        self.assertTrue(result["checkout_url"].startswith("https://app.example.test/my/orders/%s" % order.id))
        base = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-BASE")
        users = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-USER-F")
        self.assertAlmostEqual(base.price_unit, 9975.0)  # 875 x 12 less 5%
        self.assertEqual(users.product_uom_qty, 2)
        self.assertAlmostEqual(users.price_unit, 570.0)  # 50 x 12 less 5%
        self.assertEqual(order.recurrance_id, self.env.ref("sgc_layer3_bridge.period_l3_annual"))
        self.assertTrue(order.require_signature)
        self.assertEqual(order.l3_state, "awaiting_payment")
        self.assertEqual(order.l3_docs_status, "pending")
        self.assertIn("waived", str(order.note))
        self.assertNotIn("hosting", str(order.note).lower())

    def test_monthly_at_list_price(self):
        self.Checkout.create_or_get_checkout(self._payload(cycle="monthly", users=6))
        order = self.env["sale.order"].search([("l3_request_id", "=", "req-0001-marinacrest")])
        base = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-BASE")
        users = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-USER-F")
        self.assertAlmostEqual(base.price_unit, 875.0)  # no discount on monthly
        self.assertAlmostEqual(users.price_unit, 50.0)
        self.assertEqual(order.recurrance_id, self.env.ref("sgc_layer3_bridge.period_l3_monthly"))
        self.assertIn("half-yearly 2.5% off, annual 5% off", str(order.note))

    def test_half_yearly_rebate(self):
        self.Checkout.create_or_get_checkout(self._payload(cycle="half_yearly", users=5))
        order = self.env["sale.order"].search([("l3_request_id", "=", "req-0001-marinacrest")])
        self.assertEqual(len(order.order_line), 1)
        self.assertAlmostEqual(order.order_line.price_unit, 5118.75)

    def test_idempotent_on_request_and_resume(self):
        first = self.Checkout.create_or_get_checkout(self._payload())
        again = self.Checkout.create_or_get_checkout(self._payload())
        resumed = self.Checkout.create_or_get_checkout(self._payload(request_id="req-0002-marinacrest"))
        self.assertTrue(again["deduplicated"])
        self.assertTrue(resumed["deduplicated"])
        self.assertEqual(first["sale_order_name"], resumed["sale_order_name"])

    def test_slug_rules(self):
        self.assertFalse(self.Checkout.slug_status("app")["available"])
        self.assertFalse(self.Checkout.slug_status("Bad_Slug")["available"])
        self.assertTrue(self.Checkout.slug_status("marinacrest")["available"])
        self.Checkout.create_or_get_checkout(self._payload())
        with self.assertRaisesRegex(UserError, "layer3_slug_taken"):
            self.Checkout.create_or_get_checkout(self._payload(request_id="req-0003-other", email="x@other.ae"))

    def test_validation_and_kill_switch(self):
        with self.assertRaises(ValidationError):
            self.Checkout.create_or_get_checkout(self._payload(users=3))
        with self.assertRaises(ValidationError):
            self.Checkout.create_or_get_checkout(self._payload(cycle="weekly"))
        with self.assertRaises(ValidationError):
            self.Checkout.create_or_get_checkout(self._payload(hosting="uae"))
        self.env["ir.config_parameter"].sudo().set_param("sgc_layer3_bridge.checkout_enabled", "False")
        with self.assertRaisesRegex(UserError, "layer3_checkout_disabled"):
            self.Checkout.create_or_get_checkout(self._payload())

    def _activate(self, slug="marinacrest", request_id="req-0001-marinacrest", payload_overrides=None):
        kwargs = {"slug": slug, "request_id": request_id}
        if payload_overrides:
            kwargs.update(payload_overrides)
        self.Checkout.create_or_get_checkout(self._payload(**kwargs))
        order = self.env["sale.order"].search([("l3_request_id", "=", request_id)])
        order.action_confirm()
        invoice = order._create_invoices()
        invoice.action_post()
        invoice.write({"payment_state": "paid"})
        invoice.invalidate_recordset()
        return order

    def test_activation_documents_and_overdue_states(self):
        order = self._activate()
        today = fields.Date.context_today(order)
        order._l3_update_states(today)
        self.assertEqual(order.l3_state, "active")
        self.assertEqual(order.l3_activated_on, today)
        events = self.env["layer3.event"].search([("order_id", "=", order.id)])
        self.assertEqual(len(events), 1)
        self.assertTrue(events.provision)
        self.assertEqual(events.payload()["docs_status"], "pending")

        # Documents never change the account state; approval turns it green.
        # Use a fresh tenant (different email, different slug) so the resume-by-email
        # branch in create_or_get_checkout can't accidentally match the first tenant.
        order2 = self._activate(
            slug="omanagrove",
            request_id="req-0002-omanagrove",
            payload_overrides={"request_id": "req-0002-omanagrove", "slug": "omanagrove",
                               "company_name": "Omangrove Holdings LLC",
                               "email": "ops@omangrove.ae", "contact_name": "O. Al-Marri"},
        )
        order2._l3_update_states(today)
        self.assertEqual(order2.l3_state, "active")
        order2._l3_submit_documents(b"%PDF-1.4 test", "licence.pdf", "application/pdf", "1234567", today + timedelta(days=365))
        self.assertEqual(order2.l3_docs_status, "submitted")
        self.assertEqual(order2.l3_state, "active")
        order2.action_l3_docs_approve()
        self.assertEqual(order2.l3_docs_status, "approved")
        self.assertEqual(self.env["layer3.event"].search([("order_id", "=", order2.id)], order="id desc", limit=1).payload()["docs_status"], "approved")

        # Renewal-state walk on the original tenant; no attachments are read (only the invoice's
        # sale-line references are touched) so production filestore rows stay out of the path.
        renewal = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": order.partner_id.id,
            "invoice_date": today,
            "invoice_date_due": today,
            "invoice_line_ids": [(0, 0, {
                "name": "Renewal",
                "quantity": 1,
                "price_unit": 2625.0,
                "sale_line_ids": [(6, 0, order.order_line.ids)],
            })],
        })
        renewal.action_post()
        self.assertIn(renewal, order.invoice_ids)
        for days, want in ((3, "grace"), (10, "read_only"), (31, "archive")):
            order._l3_update_states(today + timedelta(days=days))
            self.assertEqual(order.l3_state, want, days)

    def test_pricing_matches_order_lines(self):
        prices = {c["cycle"]: c for c in self.Checkout.pricing()["cycles"]}
        self.assertAlmostEqual(prices["monthly"]["base_price"], 875.0)
        self.assertEqual(prices["monthly"]["rebate_percent"], 0)
        self.assertAlmostEqual(prices["quarterly"]["base_price"], 2625.0)
        self.assertAlmostEqual(prices["annual"]["base_price"], 9975.0)
        self.assertAlmostEqual(prices["annual"]["extra_user_price"], 570.0)
        self.Checkout.create_or_get_checkout(self._payload())
        order = self.env["sale.order"].search([("l3_request_id", "=", "req-0001-marinacrest")])
        base = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-BASE")
        self.assertAlmostEqual(base.price_unit, prices["annual"]["base_price"])

    def test_pricing_exposes_setup_fee(self):
        prices = self.Checkout.pricing()
        self.assertEqual(prices["setup"]["currency"], prices["currency"])
        self.assertEqual(prices["setup"]["unit_price"], 1500.0)
        self.assertTrue(prices["setup"]["waived"])  # founding cohort is the default in tests

    def test_setup_fee_waived_for_founding_and_sales_assisted_otherwise(self):
        order = self._activate()  # founding = True by default (no previous order)
        # sttl_sale_subscription cannot mix one-time and recurring lines, so the waived fee
        # lives in the Order Form terms, not as an order line.
        setup = order.order_line.filtered(lambda l: l.product_id.default_code == "L3-SETUP")
        self.assertFalse(setup)
        self.assertIn("waived", str(order.note).lower())
        # Past the founding cohort the fee is billable, so signup becomes sales-assisted.
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", "0")
        with self.assertRaisesRegex(UserError, "layer3_sales_assisted"):
            self.Checkout.create_or_get_checkout(
                self._payload(slug="harbourview", request_id="req-0009-harbourview", email="ops@harbourview.ae")
            )

    def test_returning_subdomain_continues_the_event_version(self):
        """The receiver drops versions it has seen for a subdomain: a second order for the
        same subdomain must not restart at 1."""
        first = self._activate()
        first.l3_state_version = 7
        second = first.copy()
        second.write({"l3_tenant_slug": first.l3_tenant_slug, "l3_state_version": 0, "l3_state": "active"})
        second._l3_sync()
        self.assertEqual(second.l3_state_version, 8)
        second._l3_sync()
        self.assertEqual(second.l3_state_version, 9)

    def test_open_quotation_holds_a_founding_seat(self):
        """Unpaid quotations count against the cohort: otherwise any number of signups made
        before the tenth payment would all keep the founding terms."""
        ICP = self.env["ir.config_parameter"].sudo()
        # Seats already used in this database (the trial is a production copy): paid tenants
        # plus open signup quotations, as _capacity counts them.
        today = fields.Date.context_today(self.env["sale.order"])
        taken = self.env["sale.order"].search_count(
            ["|", ("l3_activated_on", "!=", False),
             "&", "&", ("l3_request_id", "!=", False), ("state", "in", ("draft", "sent")),
             "|", ("validity_date", "=", False), ("validity_date", ">=", today)]
        )
        ICP.set_param("sgc_layer3_bridge.founding_cohort_size", str(taken + 1))
        self.assertTrue(self.Checkout.pricing()["self_serve"])
        self.Checkout.create_or_get_checkout(self._payload())  # quotation only, not paid
        self.assertFalse(self.Checkout.pricing()["self_serve"])
        with self.assertRaisesRegex(UserError, "layer3_sales_assisted"):
            self.Checkout.create_or_get_checkout(
                self._payload(slug="harbourview", request_id="req-0009-harbourview", email="ops@harbourview.ae")
            )
        # The first client retrying still resumes their own quotation.
        again = self.Checkout.create_or_get_checkout(self._payload(request_id="req-0002-marinacrest"))
        self.assertTrue(again["deduplicated"])

    def test_uae_customer_gets_an_emirate(self):
        """The UAE VAT fiscal positions are per emirate; without one a UAE client is billed 0%."""
        self.Checkout.create_or_get_checkout(self._payload())
        order = self.env["sale.order"].search([("l3_request_id", "=", "req-0001-marinacrest")])
        dubai = self.env["res.country.state"].search([("country_id.code", "=", "AE"), ("code", "=", "DU")], limit=1)
        if dubai:
            self.assertEqual(order.partner_id.state_id, dubai)
        with self.assertRaises(ValidationError):
            self.Checkout.create_or_get_checkout(
                self._payload(request_id="req-0009-otherco", slug="otherco", email="a@otherco.ae", emirate="XX")
            )

    def test_missed_renewal_is_caught_up_once(self):
        order = self._activate()
        today = fields.Date.context_today(order)
        before = order.invoice_ids
        order.write({"next_invoice_date": today - timedelta(days=3), "subscription_status": "b"})
        self.env["sale.order"]._l3_catch_up_renewals(today)
        new = order.invoice_ids - before
        self.assertEqual(len(new), 1)
        self.assertEqual(new.state, "posted")
        self.assertGreater(order.next_invoice_date, today)
        self.env["sale.order"]._l3_catch_up_renewals(today)
        self.assertEqual(len(order.invoice_ids - before), 1, "a second run must not invoice again")

    def _payload(self, **kw):
        values = {
            "request_id": "req-0001-marinacrest",
            "slug": "marinacrest",
            "company_name": "Marina Crest Real Estate LLC",
            "contact_name": "A. Rahman",
            "email": "ops@marinacrest.ae",
            "cycle": "annual",
            "users": 7,
            "mobile": "+971 50 000 0000",
            "trade_licence_no": "1234567",
        }
        values.update(kw)
        return values
