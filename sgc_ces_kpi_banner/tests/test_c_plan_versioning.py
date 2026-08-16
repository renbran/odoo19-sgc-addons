# -*- coding: utf-8 -*-
"""Category C - plan versioning and resolution hierarchy."""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestPlanVersioning(CesKpiCase):
    def test_active_assigned_plan_is_frozen(self):
        plan = self._make_plan(code="ver_freeze")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        self._make_assignment(plan)
        with self.assertRaises(UserError):
            plan.write({"start_date_strategy": "contract_start"})

    def test_cosmetic_edits_still_allowed(self):
        plan = self._make_plan(code="ver_cosmetic")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        self._make_assignment(plan)
        plan.write({"name": "Renamed", "description": "still editable"})
        self.assertEqual(plan.name, "Renamed")

    def test_new_version_copies_tree_and_supersedes(self):
        plan = self._make_plan(code="ver_new")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        action = plan.action_new_version()
        new_plan = self.env["sgc.ces.gate.plan"].browse(action["res_id"])
        self.assertEqual(new_plan.version, plan.version + 1)
        self.assertEqual(new_plan.state, "draft")
        self.assertEqual(len(new_plan.template_ids), 1)
        self.assertEqual(len(new_plan.template_ids.requirement_ids), 1)
        new_plan.action_activate()
        self.assertEqual(plan.state, "superseded")

    def test_plan_with_assignments_cannot_be_deleted(self):
        plan = self._make_plan(code="ver_del")
        template = self._make_template(plan, code="g1")
        self._make_requirement(template)
        plan.action_activate()
        self._make_assignment(plan)
        with self.assertRaises(UserError):
            plan.unlink()

    def test_activation_requires_a_template(self):
        plan = self._make_plan(code="ver_empty")
        with self.assertRaises(UserError):
            plan.action_activate()

    def test_resolution_returns_the_one_active_default_plan(self):
        default_plan = self._make_plan(code="ver_default", is_default=True)
        self._make_requirement(self._make_template(default_plan, code="g1"))
        default_plan.action_activate()

        resolved = self.env["sgc.ces.gate.plan"]._resolve_plan_for_employee(self.ces_employee)
        self.assertEqual(resolved, default_plan)
        resolved_other = self.env["sgc.ces.gate.plan"]._resolve_plan_for_employee(self.other_employee)
        self.assertEqual(resolved_other, default_plan)

    def test_historical_instances_keep_old_targets(self):
        plan = self._make_plan(code="ver_hist")
        template = self._make_template(plan, code="g1")
        requirement = self._make_requirement(template, target_value=500.0)
        plan.action_activate()
        assignment = self._make_assignment(plan)
        result = assignment.instance_ids.result_ids
        self.assertEqual(result.original_target, 500.0)

        action = plan.action_new_version()
        new_plan = self.env["sgc.ces.gate.plan"].browse(action["res_id"])
        new_plan.template_ids.requirement_ids.write({"target_value": 9999.0})
        # The already-generated instance is untouched.
        self.assertEqual(result.original_target, 500.0)
        self.assertEqual(requirement.target_value, 500.0)
