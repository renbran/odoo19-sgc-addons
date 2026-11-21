# SPDX-License-Identifier: OPL-1
"""Registered payments become statement lines that end up reconciled, and the payments become matched."""
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "pay_rec")
class TestReconcileFromPayments(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", cls.env.company.id)], limit=1)
        cls.partner = cls.env["res.partner"].create({"name": "PAYREC Customer"})

    def _payment(self, ptype, amount):
        pay = self.env["account.payment"].create({
            "payment_type": ptype, "partner_type": "customer" if ptype == "inbound" else "supplier",
            "partner_id": self.partner.id, "amount": amount, "journal_id": self.journal.id,
        })
        pay.action_post()
        return pay

    def test_receipt_and_payment_reconciled(self):
        rec, out = self._payment("inbound", 1500.0), self._payment("outbound", 400.0)
        self.assertFalse(rec.is_matched)
        stmt = self.journal._reconcile_from_payments()
        self.assertEqual(len(stmt.line_ids), 2)
        self.assertEqual(sorted(stmt.line_ids.mapped("amount")), [-400.0, 1500.0])
        self.assertTrue(all(stmt.line_ids.mapped("is_reconciled")))
        self.assertTrue(rec.is_matched and out.is_matched)
        self.assertEqual(stmt.attachment_ids.mimetype, "text/csv", "CSV export must be attached")
        # idempotent: nothing left to reconcile
        self.assertFalse(self.journal._reconcile_from_payments())
