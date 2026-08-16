# -*- coding: utf-8 -*-
"""Category D - requirement semantics, scoring and the no-eval contract."""
import json
import re

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from ..models import metric_registry
from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestRequirements(CesKpiCase):
    def test_dispatch_table_is_closed(self):
        with self.assertRaises(UserError):
            self.Registry.evaluate("../../etc/passwd", {"user_id": self.ces_user.id})
        with self.assertRaises(UserError):
            self.Registry.evaluate("__import__('os').system", {"user_id": self.ces_user.id})

    def test_every_selection_entry_has_a_provider(self):
        for code, _label in metric_registry.METRIC_SELECTION:
            self.assertIn(code, metric_registry.METRIC_DISPATCH, code)
            model_name, method = metric_registry.METRIC_DISPATCH[code]
            self.assertTrue(hasattr(self.env[model_name], method), code)

    def test_no_eval_in_metric_layer_source(self):
        """Static guard: the metric layer must never gain a dynamic evaluator."""
        import inspect
        from ..models import (
            metric_activity,
            metric_payment,
            metric_pipeline,
            metric_signature,
            metric_staleness,
        )

        for module in (
            metric_registry,
            metric_activity,
            metric_payment,
            metric_pipeline,
            metric_signature,
            metric_staleness,
        ):
            source = inspect.getsource(module)
            for pattern in (
                r"eval\s*\(",
                r"exec\s*\(",
                r"safe_eval\s*\(",
                r"cr\.execute\s*\(",
            ):
                self.assertIsNone(
                    re.search(pattern, source),
                    "%s found in %s" % (pattern, module.__name__),
                )

    def test_comparators(self):
        self.assertTrue(metric_registry.compare(5, ">=", 5))
        self.assertFalse(metric_registry.compare(4, ">=", 5))
        self.assertTrue(metric_registry.compare(4, "<", 5))
        self.assertTrue(metric_registry.compare(5, "==", 5))
        self.assertTrue(metric_registry.compare(6, "!=", 5))
        with self.assertRaises(UserError):
            metric_registry.compare(1, "~=", 1)

    def test_progress_ratio_direction_aware(self):
        self.assertEqual(metric_registry.progress_ratio(50, ">=", 100), 0.5)
        self.assertEqual(metric_registry.progress_ratio(150, ">=", 100), 1.0)
        self.assertEqual(metric_registry.progress_ratio(5, "<=", 10), 1.0)
        self.assertEqual(metric_registry.progress_ratio(20, "<=", 10), 0.0)

    def test_mandatory_cannot_be_averaged_away(self):
        plan = self._make_plan(code="req_mand")
        template = self._make_template(plan, code="g1", pass_threshold=50.0)
        self._make_requirement(template, name="Mandatory", target_value=1000000.0,
                               level="mandatory")
        self._make_requirement(template, name="Weighted", metric_code="activity_logged_count",
                               target_value=0.0, level="weighted", comparator=">=")
        plan.action_activate()
        assignment = self._make_assignment(plan)
        instance = assignment.instance_ids
        instance.evaluate()
        self.assertFalse(instance.mandatory_met)
        self.assertEqual(instance.projected_outcome, "fail")

    def test_informational_requirement_does_not_move_the_score(self):
        plan = self._make_plan(code="req_info")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template, name="Weighted", metric_code="activity_logged_count",
                               target_value=0.0, level="weighted")
        self._make_requirement(template, name="Info", target_value=1000000.0,
                               level="informational")
        plan.action_activate()
        assignment = self._make_assignment(plan)
        instance = assignment.instance_ids
        instance.evaluate()
        self.assertEqual(instance.score, 100.0)

    def test_params_are_json_data_not_code(self):
        plan = self._make_plan(code="req_params")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template, stale_days=45)
        plan.action_activate()
        assignment = self._make_assignment(plan)
        raw = assignment.instance_ids.result_ids.params_json
        data = json.loads(raw)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["stale_days"], 45)

    def test_invalid_order_state_is_rejected(self):
        plan = self._make_plan(code="req_states")
        template = self._make_template(plan, code="g1")
        with self.assertRaises(ValidationError):
            self._make_requirement(template, metric_code="signed_proposal_count",
                                   order_states="sale,not_a_state")

    def test_negative_stale_days_rejected(self):
        plan = self._make_plan(code="req_stale")
        template = self._make_template(plan, code="g1")
        with self.assertRaises(ValidationError):
            self._make_requirement(template, stale_days=0)

    def test_template_schedule_validation(self):
        plan = self._make_plan(code="req_sched")
        with self.assertRaises(ValidationError):
            self._make_template(plan, code="bad", duration_months=0)
        with self.assertRaises(ValidationError):
            self._make_template(plan, code="bad2", offset_months=-1)
