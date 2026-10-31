# -*- coding: utf-8 -*-
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests.common import TransactionCase, tagged

from ..models.checkout import PACKAGES, SaleOrder

ONE_PIXEL_PNG = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

PAYLOAD = {
    "request_id": "test-acc-0001",
    "package": "start",
    "cycle": "monthly",
    "company_name": "Gulf Example Trading LLC",
    "contact_name": "Amina Example",
    "email": "amina.example@gulf-example.test",
    "trn": "100000000000003",
    "emirate": "DU",
}


@tagged("post_install", "-at_install")
class TestAccountingCheckout(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Environment-independent 5% VAT on the package products for this company.
        tax = cls.env["account.tax"].create({
            "name": "VAT 5% (checkout test)",
            "amount": 5,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.env.company.id,
        })
        for xmlid in ["product_acc_onboarding"] + [x for _label, x in PACKAGES.values()]:
            cls.env.ref("sgc_accounting_checkout.%s" % xmlid).taxes_id = [(6, 0, tax.ids)]
        cls.Checkout = cls.env["sgc.accounting.checkout"]

    def _order(self, result):
        return self.env["sale.order"].search([("name", "=", result["sale_order_name"])])

    def test_monthly_quotation_is_sign_and_pay_with_no_trial(self):
        result = self.Checkout.create_checkout(dict(PAYLOAD))
        order = self._order(result)
        self.assertEqual(order.state, "sent")
        self.assertTrue(order.require_payment)
        self.assertTrue(order.require_signature)
        self.assertEqual(order.prepayment_percent, 1.0)
        self.assertAlmostEqual(order.amount_untaxed, 399 + 500)
        self.assertAlmostEqual(order.amount_tax, (399 + 500) * 0.05)
        self.assertIn(order.get_portal_url(), result["checkout_url"])
        # Same request id -> same order, never a second one.
        again = self.Checkout.create_checkout(dict(PAYLOAD))
        self.assertTrue(again["deduplicated"])
        self.assertEqual(again["sale_order_name"], result["sale_order_name"])

    def test_annual_is_twelve_for_eleven(self):
        payload = dict(PAYLOAD, request_id="test-acc-0002", package="growth_cfo", cycle="annual")
        order = self._order(self.Checkout.create_checkout(payload))
        package_line = order.order_line.filtered(lambda l: l.product_id.default_code == "ACC-GROWTH-CFO")
        self.assertEqual(package_line.product_uom_qty, 11)
        self.assertAlmostEqual(order.amount_untaxed, 1999 * 11 + 500)

    def test_bad_input_is_refused(self):
        for bad in ({"package": "free_trial"}, {"trn": "12345"}, {"email": "not-an-email"}, {"cycle": "weekly"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-bad", **bad))

    def test_internal_email_is_refused(self):
        staff = self.env["res.users"].create({
            "name": "Staff Example", "login": "staff.example@sgctech.test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(UserError):
            self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0003", email=staff.login))

    def test_portal_opens_only_when_confirmed_and_paid(self):
        order = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0004")))

        # Paid but not confirmed: nothing.
        with patch.object(SaleOrder, "_acc_is_paid", return_value=True):
            self.env["sale.order"]._acc_cron_activate()
        self.assertFalse(order.acc_client_id)

        # Confirmed but not paid (e.g. confirmed by hand): nothing.
        order.action_confirm()
        self.assertEqual(order.state, "sale")
        self.assertFalse(order.acc_client_id)
        self.assertFalse(order.partner_id.user_ids)

        # Payment validated: the cron opens the portal.
        with patch.object(SaleOrder, "_acc_is_paid", return_value=True):
            self.env["sale.order"]._acc_cron_activate()
        client = order.acc_client_id
        self.assertTrue(client)
        self.assertEqual(client.partner_id, order.partner_id.commercial_partner_id)
        self.assertEqual(client.client_code, "gulf-example-trading-llc")
        self.assertEqual(client.trn, PAYLOAD["trn"])
        self.assertEqual(client.status, "queued")
        user = order.partner_id.user_ids
        self.assertEqual(user.login, PAYLOAD["email"])
        self.assertTrue(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_user"))

        # Idempotent: a second run creates nothing new.
        with patch.object(SaleOrder, "_acc_is_paid", return_value=True):
            self.env["sale.order"]._acc_cron_activate()
        self.assertEqual(self.env["sgc.accounting.client"].search_count([("partner_id", "=", client.partner_id.id)]), 1)

    def test_confirm_after_payment_opens_portal_in_same_request(self):
        order = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0005")))
        with patch.object(SaleOrder, "_acc_is_paid", return_value=True):
            order.action_confirm()  # what payment post-processing does for a 'done' transaction
        self.assertTrue(order.acc_client_id)
        self.assertTrue(order.partner_id.user_ids.has_group("base.group_portal"))

    def test_real_done_transaction_confirms_order_and_opens_portal(self):
        """The exact chain sale runs for a settled card payment, no patching."""
        order = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0007")))
        provider = self.env["payment.provider"].create({"name": "Test card", "code": "none", "state": "test"})
        method = self.env["payment.method"].with_context(active_test=False).search([], limit=1)
        tx = self.env["payment.transaction"].create({
            "provider_id": provider.id,
            "payment_method_id": method.id,
            "reference": order.name,
            "amount": order.amount_total,
            "currency_id": order.currency_id.id,
            "partner_id": order.partner_id.id,
            "sale_order_ids": [(6, 0, order.ids)],
        })
        tx._set_pending()
        tx._check_amount_and_confirm_order()  # pending: must not confirm or open anything
        self.assertEqual(order.state, "sent")
        self.assertFalse(order.acc_client_id)
        # Sign & Pay: the portal takes the signature before the card form. (Some 19.0 builds
        # also refuse to confirm an unsigned paid quotation; others don't — signing first is
        # the real flow either way.)
        order.write({"signature": ONE_PIXEL_PNG, "signed_by": "Amina Example"})
        tx._set_done()
        # amount_paid depends on transaction_ids only, not their state; in production the
        # done notification is a separate request with a fresh cache.
        order.invalidate_recordset(["amount_paid"])
        tx._check_amount_and_confirm_order()  # what sale's _post_process does for a done tx
        self.assertEqual(order.state, "sale")
        self.assertTrue(order.acc_client_id)
        self.assertTrue(order.partner_id.user_ids.has_group("base.group_portal"))

    def test_only_the_integration_user_may_call(self):
        portal = self.env["res.users"].create({
            "name": "Portal Example", "login": "portal.example@other.test",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        with self.assertRaises(AccessError):
            self.Checkout.with_user(portal).create_checkout(dict(PAYLOAD, request_id="test-acc-0010"))
        machine = self.env["res.users"].create({
            "name": "Website Machine", "login": "website-machine@sgctech.test",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id,
                                  self.env.ref("sgc_accounting_checkout.group_accounting_checkout_integration").id])],
        })
        result = self.Checkout.with_user(machine).create_checkout(dict(PAYLOAD, request_id="test-acc-0011"))
        self.assertTrue(result["ok"])

    def test_existing_login_is_never_reused_or_reactivated(self):
        revoked = self.env["res.users"].create({
            "name": "Former Employee", "login": "former@customer-x.test",
            "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        revoked.active = False
        for email in ("former@customer-x.test", PAYLOAD["email"]):
            if email == PAYLOAD["email"]:  # an active portal login, created by an earlier signup
                self.env["res.users"].create({
                    "name": "Amina", "login": email,
                    "group_ids": [(6, 0, [self.env.ref("base.group_portal").id])],
                })
            with self.subTest(email=email), self.assertRaises(UserError):
                self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-%s" % email[:6], email=email))
        self.assertFalse(revoked.active)

    def test_resubmission_replaces_the_open_quotation(self):
        first = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0012")))
        second = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0013", package="business")))
        self.assertEqual(first.state, "cancel")
        self.assertEqual(second.state, "sent")

    def test_reused_request_id_with_other_details_is_refused(self):
        self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0014"))
        with self.assertRaises(ValidationError):
            self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0014", email="other@gulf-example.test"))

    def test_partial_payment_then_manual_confirm_does_not_open_portal(self):
        order = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0015")))
        provider = self.env["payment.provider"].create({"name": "Test card", "code": "none", "state": "test"})
        method = self.env["payment.method"].with_context(active_test=False).search([], limit=1)
        tx = self.env["payment.transaction"].create({
            "provider_id": provider.id, "payment_method_id": method.id, "reference": order.name + "-1",
            "amount": 1.0, "currency_id": order.currency_id.id, "partner_id": order.partner_id.id,
            "sale_order_ids": [(6, 0, order.ids)],
        })
        tx._set_done()
        order.action_confirm()  # staff confirm by hand
        self.env["sale.order"]._acc_cron_activate()
        self.assertFalse(order.acc_client_id)
        self.assertFalse(order._acc_is_paid())

    def test_paid_check_needs_money(self):
        order = self._order(self.Checkout.create_checkout(dict(PAYLOAD, request_id="test-acc-0006")))
        order.action_confirm()
        self.assertFalse(order._acc_is_paid())

    def test_client_code_is_unique_and_valid(self):
        Order = self.env["sale.order"]
        self.assertEqual(Order._acc_client_code("Demo"), "client-demo")
        self.assertEqual(Order._acc_client_code("شركة"), "client")
        partner = self.env["res.partner"].create({"name": "Taken"})
        self.env["sgc.accounting.client"].create({"name": "Taken", "client_code": "taken-co", "partner_id": partner.id})
        self.assertEqual(Order._acc_client_code("Taken Co"), "taken-co-2")


@tagged("post_install", "-at_install")
class TestAccountingRenewals(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        tax = cls.env["account.tax"].create({
            "name": "VAT 5% (renewal test)",
            "amount": 5,
            "amount_type": "percent",
            "type_tax_use": "sale",
            "company_id": cls.env.company.id,
        })
        for xmlid in ["product_acc_onboarding"] + [x for _label, x in PACKAGES.values()]:
            cls.env.ref("sgc_accounting_checkout.%s" % xmlid).taxes_id = [(6, 0, tax.ids)]

    def _active_order(self, request_id, cycle="monthly", package="start"):
        # The invoicing test base runs as an accountant, not superuser; the website caller is checked elsewhere.
        result = self.env["sgc.accounting.checkout"].sudo().create_checkout(dict(
            PAYLOAD, request_id=request_id, cycle=cycle, package=package, email="%s@renewal.test" % request_id,
        ))
        order = self.env["sale.order"].search([("name", "=", result["sale_order_name"])])
        with patch.object(SaleOrder, "_acc_is_paid", return_value=True):
            order.action_confirm()
        self.assertTrue(order.acc_client_id)
        return order

    def _renewals(self, order):
        return self.env["account.move"].search([("invoice_origin", "=", order.name), ("move_type", "=", "out_invoice")])

    def test_monthly_renewal_is_invoiced_when_the_paid_month_ends(self):
        order = self._active_order("renew-0001")
        today = fields.Date.context_today(order)
        self.assertEqual(order.acc_paid_until, today + relativedelta(months=1))
        Order = self.env["sale.order"]
        Order._acc_cron_renew(today=order.acc_paid_until - relativedelta(days=1))
        self.assertFalse(self._renewals(order))

        Order._acc_cron_renew(today=order.acc_paid_until)
        invoice = self._renewals(order)
        self.assertEqual(len(invoice), 1)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.partner_id, order.partner_invoice_id)
        self.assertAlmostEqual(invoice.amount_untaxed, 399)
        self.assertAlmostEqual(invoice.amount_tax, 19.95)
        self.assertTrue(invoice.is_move_sent)
        self.assertEqual(order.acc_paid_until, today + relativedelta(months=2))

        Order._acc_cron_renew(today=today + relativedelta(months=1))  # same day again
        self.assertEqual(len(self._renewals(order)), 1)

    def test_annual_renewal_is_twelve_for_eleven_and_catches_up(self):
        order = self._active_order("renew-0002", cycle="annual", package="growth_cfo")
        start = order.acc_paid_until
        self.assertEqual(start, fields.Date.context_today(order) + relativedelta(months=12))
        self.env["sale.order"]._acc_cron_renew(today=start + relativedelta(months=12))  # a whole year missed
        invoices = self._renewals(order)
        self.assertEqual(len(invoices), 2)
        self.assertEqual(invoices.mapped("amount_untaxed"), [1999 * 11] * 2)
        self.assertEqual(order.acc_paid_until, start + relativedelta(months=24))

    def test_no_renewal_after_notice_or_suspension(self):
        order = self._active_order("renew-0003")
        Order = self.env["sale.order"]
        order.acc_renewal_active = False
        Order._acc_cron_renew(today=order.acc_paid_until)
        self.assertFalse(self._renewals(order))
        order.acc_renewal_active = True
        order.acc_client_id.status = "suspended"
        Order._acc_cron_renew(today=order.acc_paid_until)
        self.assertFalse(self._renewals(order))
