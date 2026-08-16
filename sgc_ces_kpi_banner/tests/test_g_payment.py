# -*- coding: utf-8 -*-
"""Category G - paid-deal metric and accounting non-disclosure."""
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestPayment(CesKpiCase):
    def _ctx(self, **kw):
        ctx = {"user_id": self.ces_user.id, "date_from": None, "date_to": None, "params": {}}
        ctx.update(kw)
        return ctx

    def test_qualifying_states_default_to_paid_only(self):
        provider = self.env["sgc.ces.metric.payment"]
        self.assertEqual(provider._qualifying_states({}), ["paid"])
        self.assertEqual(
            provider._qualifying_states({"qualifying_payment_mode": "paid_partial"}),
            ["paid", "partial"],
        )
        self.assertEqual(
            provider._qualifying_states({"qualifying_payment_mode": "paid_inclusive"}),
            ["paid", "partial", "in_payment"],
        )

    def test_unknown_mode_falls_back_to_paid(self):
        provider = self.env["sgc.ces.metric.payment"]
        self.assertEqual(
            provider._qualifying_states({"qualifying_payment_mode": "anything"}), ["paid"]
        )

    def test_won_stage_alone_never_counts_as_paid(self):
        won = self.env["crm.stage"].create({"name": "Test Won Stage", "is_won": True})
        self._make_lead(self.ces_user, revenue=10000.0, stage=won)
        result = self.Registry.evaluate("paid_deal_count", self._ctx())
        self.assertEqual(result["value"], 0.0)

    def test_drilldown_never_targets_an_accounting_model(self):
        result = self.Registry.evaluate("paid_deal_count", self._ctx())
        self.assertEqual(result["res_model"], "sale.order")
        self.assertNotIn("account", (result["res_model"] or ""))

    def test_detail_exposes_no_accounting_identifiers(self):
        result = self.Registry.evaluate("paid_deal_value", self._ctx())
        detail = result.get("detail") or {}
        self.assertEqual(set(detail.keys()), {"qualifying_payment_states"})
        for key in detail:
            self.assertNotIn("invoice", key)
            self.assertNotIn("move", key)
            self.assertNotIn("journal", key)

    def test_paid_metrics_are_aggregate_only(self):
        for code in ("paid_deal_count", "paid_deal_value"):
            result = self.Registry.evaluate(code, self._ctx())
            self.assertIsInstance(result["value"], float)
            self.assertNotIn("invoice_ids", result)
            self.assertNotIn("move_ids", result)

    def test_empty_result_is_safe_domain(self):
        result = self.Registry.evaluate("paid_deal_count", self._ctx())
        self.assertEqual(result["domain"], [("id", "=", 0)])
