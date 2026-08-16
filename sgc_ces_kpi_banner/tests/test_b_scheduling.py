# -*- coding: utf-8 -*-
"""Category B - gate scheduling maths (month overflow, leap years, weekends)."""
from odoo import fields
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestScheduling(CesKpiCase):
    def _template(self, **kw):
        plan = self._make_plan(code="sched_%s" % (kw.get("code") or "a"))
        return self._make_template(plan, **{k: v for k, v in kw.items() if k != "code"})

    def test_jan_31_plus_one_month_clamps_to_february(self):
        template = self._template(offset_months=0, duration_months=1)
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2026-01-31"))
        self.assertEqual(due, fields.Date.to_date("2026-02-28"))

    def test_jan_31_plus_one_month_in_leap_year(self):
        template = self._template(code="b", offset_months=0, duration_months=1)
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2024-01-31"))
        self.assertEqual(due, fields.Date.to_date("2024-02-29"))

    def test_feb_29_plus_twelve_months_clamps(self):
        template = self._template(code="c", offset_months=0, duration_months=12)
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2024-02-29"))
        self.assertEqual(due, fields.Date.to_date("2025-02-28"))

    def test_offset_and_duration_stack(self):
        template = self._template(code="d", offset_months=2, duration_months=1)
        start, end, due, _r = template.compute_schedule(fields.Date.to_date("2026-01-15"))
        self.assertEqual(start, fields.Date.to_date("2026-03-15"))
        self.assertEqual(end, fields.Date.to_date("2026-04-15"))
        self.assertEqual(due, end)

    def test_end_of_month_policy(self):
        template = self._template(code="e", offset_months=0, duration_months=1,
                                  due_day_policy="end_of_month")
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2026-01-10"))
        self.assertEqual(due, fields.Date.to_date("2026-02-28"))

    def test_working_day_adjustment_next(self):
        # 2026-02-28 is a Saturday.
        template = self._template(code="f", offset_months=0, duration_months=1,
                                  working_day_adjustment="next")
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2026-01-31"))
        self.assertEqual(due.weekday() < 5, True)
        self.assertEqual(due, fields.Date.to_date("2026-03-02"))

    def test_working_day_adjustment_previous(self):
        template = self._template(code="g", offset_months=0, duration_months=1,
                                  working_day_adjustment="previous")
        _s, _e, due, _r = template.compute_schedule(fields.Date.to_date("2026-01-31"))
        self.assertEqual(due, fields.Date.to_date("2026-02-27"))

    def test_review_date_is_lead_days_before_due(self):
        template = self._template(code="h", offset_months=0, duration_months=1,
                                  review_lead_days=7)
        _s, _e, due, review = template.compute_schedule(fields.Date.to_date("2026-01-31"))
        self.assertEqual((due - review).days, 7)

    def test_instance_generation_is_idempotent(self):
        plan = self._make_plan(code="sched_idem")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        assignment = self._make_assignment(plan)
        first = len(assignment.instance_ids)
        assignment.generate_instances()
        self.assertEqual(len(assignment.instance_ids), first)
        self.assertEqual(first, 1)

    def test_instance_snapshots_schedule(self):
        plan = self._make_plan(code="sched_snap")
        template = self._make_template(plan, code="g1", offset_months=0, duration_months=1)
        self._make_requirement(template)
        plan.action_activate()
        assignment = self._make_assignment(plan)
        instance = assignment.instance_ids
        self.assertEqual(instance.anchor_date, fields.Date.to_date("2026-01-31"))
        self.assertEqual(instance.due_date, fields.Date.to_date("2026-02-28"))
        self.assertEqual(instance.review_date, fields.Date.to_date("2026-02-21"))
