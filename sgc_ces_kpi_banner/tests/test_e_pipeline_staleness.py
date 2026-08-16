# -*- coding: utf-8 -*-
"""Category E - pipeline and staleness metrics, including day boundaries."""
from datetime import timedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestPipelineStaleness(CesKpiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_open = cls.env["crm.stage"].create({"name": "Test Open Stage"})
        cls.stage_dead = cls.env["crm.stage"].create({"name": "Test No Answer Stage"})
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.excluded_stage_ids", str(cls.stage_dead.id)
        )

    def _ctx(self, **kw):
        ctx = {
            "user_id": self.ces_user.id,
            "date_from": None,
            "date_to": fields.Date.context_today(self.env["sgc.ces.identity"]),
            "params": {},
        }
        ctx.update(kw)
        return ctx

    def test_pipeline_value_sums_open_opportunities(self):
        self._make_lead(self.ces_user, revenue=1500.0, stage=self.stage_open)
        self._make_lead(self.ces_user, revenue=2500.0, stage=self.stage_open)
        result = self.Registry.evaluate("pipeline_qualified_value", self._ctx())
        self.assertEqual(result["value"], 4000.0)
        self.assertEqual(result["res_model"], "crm.lead")

    def test_pipeline_excludes_dead_end_stages(self):
        self._make_lead(self.ces_user, revenue=1000.0, stage=self.stage_open)
        self._make_lead(self.ces_user, revenue=9999.0, stage=self.stage_dead)
        result = self.Registry.evaluate("pipeline_qualified_value", self._ctx())
        self.assertEqual(result["value"], 1000.0)

    def test_pipeline_ignores_other_users(self):
        self._make_lead(self.other_user, revenue=5000.0, stage=self.stage_open)
        result = self.Registry.evaluate("pipeline_qualified_value", self._ctx())
        self.assertEqual(result["value"], 0.0)

    def test_pipeline_minimum_revenue_filter(self):
        self._make_lead(self.ces_user, revenue=100.0, stage=self.stage_open)
        self._make_lead(self.ces_user, revenue=5000.0, stage=self.stage_open)
        result = self.Registry.evaluate(
            "pipeline_qualified_value", self._ctx(params={"min_expected_revenue": 1000.0})
        )
        self.assertEqual(result["value"], 5000.0)

    def test_pipeline_count_metric(self):
        self._make_lead(self.ces_user, revenue=1.0, stage=self.stage_open)
        self._make_lead(self.ces_user, revenue=2.0, stage=self.stage_open)
        result = self.Registry.evaluate("pipeline_qualified_count", self._ctx())
        self.assertEqual(result["value"], 2.0)

    # -- staleness ----------------------------------------------------------
    def test_default_staleness_field_is_date_last_stage_update(self):
        provider = self.env["sgc.ces.metric.staleness"]
        self.assertEqual(provider._source_field({}), "date_last_stage_update")
        self.assertEqual(
            provider._source_field({"staleness_field": "x_days_since_activity"}),
            "date_last_stage_update",
            "the dead field must never be honoured",
        )

    def test_stale_day_boundary_exclusive(self):
        """Exactly stale_days old is NOT stale; one day more is."""
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        exactly = fields.Datetime.to_string(
            fields.Datetime.to_datetime(today - timedelta(days=45))
        )
        older = fields.Datetime.to_string(
            fields.Datetime.to_datetime(today - timedelta(days=46))
        )
        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=exactly)
        result = self.Registry.evaluate(
            "staleness_stale_count", self._ctx(params={"stale_days": 45})
        )
        self.assertEqual(result["value"], 0.0)

        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=older)
        result = self.Registry.evaluate(
            "staleness_stale_count", self._ctx(params={"stale_days": 45})
        )
        self.assertEqual(result["value"], 1.0)

    def test_staleness_bands(self):
        today = fields.Date.context_today(self.env["sgc.ces.identity"])

        def stamp(days):
            return fields.Datetime.to_string(
                fields.Datetime.to_datetime(today - timedelta(days=days))
            )

        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=stamp(1))
        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=stamp(35))
        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=stamp(60))
        bands = self.env["sgc.ces.metric.staleness"]._band_counts(
            self._ctx(params={"stale_days": 45, "warn_days": 30})
        )
        self.assertEqual(bands["stale"], 1)
        self.assertEqual(bands["at_risk"], 1)
        self.assertEqual(bands["healthy"], 1)

    def test_stale_ratio_ignores_unknowns(self):
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        stamp = fields.Datetime.to_string(
            fields.Datetime.to_datetime(today - timedelta(days=60))
        )
        self._make_lead(self.ces_user, 1.0, self.stage_open, last_stage_update=stamp)
        result = self.Registry.evaluate(
            "staleness_stale_ratio", self._ctx(params={"stale_days": 45})
        )
        self.assertEqual(result["value"], 100.0)

    def test_healthy_ratio_with_no_data_is_zero_not_error(self):
        result = self.Registry.evaluate("staleness_healthy_ratio", self._ctx())
        self.assertEqual(result["value"], 0.0)
        self.assertNotIn("error", result)

    def test_window_resolution(self):
        registry = self.Registry
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        date_from, date_to = registry.resolve_window("current_day")
        self.assertEqual(date_from, today)
        self.assertEqual(date_to, today)
        date_from, _ = registry.resolve_window("current_month")
        self.assertEqual(date_from.day, 1)
        date_from, _ = registry.resolve_window("rolling_days", params={"window_days": 7})
        self.assertEqual((today - date_from).days, 7)
        date_from, _ = registry.resolve_window("all_time")
        self.assertIsNone(date_from)
