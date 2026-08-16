# -*- coding: utf-8 -*-
"""Category F - signed-proposal metric."""
from odoo import fields
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestSignature(CesKpiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "CES Test Customer"})

    def _ctx(self, **kw):
        ctx = {
            "user_id": self.ces_user.id,
            "date_from": None,
            "date_to": None,
            "params": {},
        }
        ctx.update(kw)
        return ctx

    def _order(self, signed=True, state="sale"):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "user_id": self.ces_user.id,
                "require_signature": True,
            }
        )
        values = {"state": state}
        if signed:
            values["signed_on"] = fields.Datetime.now()
        order.sudo().write(values)
        return order

    def test_native_strategy_counts_signed_orders(self):
        self._order(signed=True)
        result = self.Registry.evaluate("signed_proposal_count", self._ctx())
        self.assertEqual(result["value"], 1.0)
        self.assertEqual(result["res_model"], "sale.order")

    def test_unsigned_order_does_not_count(self):
        self._order(signed=False)
        result = self.Registry.evaluate("signed_proposal_count", self._ctx())
        self.assertEqual(result["value"], 0.0)

    def test_other_users_orders_are_excluded(self):
        order = self._order(signed=True)
        order.sudo().write({"user_id": self.other_user.id})
        result = self.Registry.evaluate("signed_proposal_count", self._ctx())
        self.assertEqual(result["value"], 0.0)

    def test_order_state_filter(self):
        self._order(signed=True, state="draft")
        result = self.Registry.evaluate(
            "signed_proposal_count", self._ctx(params={"order_states": "sale"})
        )
        self.assertEqual(result["value"], 0.0)
        result = self.Registry.evaluate(
            "signed_proposal_count", self._ctx(params={"order_states": "draft"})
        )
        self.assertEqual(result["value"], 1.0)

    def test_require_opportunity_filter(self):
        self._order(signed=True)
        result = self.Registry.evaluate(
            "signed_proposal_count", self._ctx(params={"require_opportunity": True})
        )
        self.assertEqual(result["value"], 0.0)

    def test_signed_value_metric(self):
        order = self._order(signed=True)
        self.assertEqual(
            self.Registry.evaluate("signed_proposal_value", self._ctx())["value"],
            order.amount_untaxed,
        )

    def test_external_strategy_degrades_when_field_absent(self):
        """The external envelope fields belong to another addon; if they are not
        installed the metric must return 0, never raise."""
        result = self.Registry.safe_evaluate(
            "signed_proposal_count", self._ctx(params={"signature_strategy": "external"})
        )
        self.assertNotIn("error", result)
        self.assertIsInstance(result["value"], float)

    def test_combined_strategy_runs(self):
        self._order(signed=True)
        result = self.Registry.safe_evaluate(
            "signed_proposal_count", self._ctx(params={"signature_strategy": "combined"})
        )
        self.assertGreaterEqual(result["value"], 1.0)

    def test_unknown_strategy_falls_back_to_native(self):
        provider = self.env["sgc.ces.metric.signature"]
        self.assertEqual(provider._strategy({"signature_strategy": "hacked"}), "native")
