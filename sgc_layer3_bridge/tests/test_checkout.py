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
            self.Checkout.create_or_get_checkout(self._payload(cycle="monthly"))
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
