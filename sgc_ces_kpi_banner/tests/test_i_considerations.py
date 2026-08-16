# -*- coding: utf-8 -*-
"""Category I - considerations are additive and never rewrite history."""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestConsiderations(CesKpiCase):
    def _gate(self, code="cons"):
        plan = self._make_plan(code=code)
        template = self._make_template(plan, code="g1")
        self._make_requirement(template, target_value=1000.0)
        plan.action_activate()
        return self._make_assignment(plan).instance_ids

    def test_extension_does_not_rewrite_due_date(self):
        instance = self._gate("cons_ext")
        original = instance.due_date
        new_due = fields.Date.add(original, days=14)
        self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": instance.id,
                "consideration_type": "extension",
                "new_due_date": new_due,
                "reason": "Onboarding delay",
                "state": "approved",
            }
        )
        self.assertEqual(instance.due_date, original)
        self.assertEqual(instance.effective_due_date(), new_due)

    def test_extension_must_be_later_than_original(self):
        instance = self._gate("cons_ext2")
        with self.assertRaises(ValidationError):
            self.env["sgc.ces.gate.consideration"].create(
                {
                    "instance_id": instance.id,
                    "consideration_type": "extension",
                    "new_due_date": fields.Date.subtract(instance.due_date, days=1),
                    "reason": "Invalid",
                }
            )

    def test_target_adjustment_preserves_original_target(self):
        instance = self._gate("cons_target")
        result = instance.result_ids
        self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": instance.id,
                "requirement_result_id": result.id,
                "consideration_type": "target_adjustment",
                "adjusted_target": 400.0,
                "reason": "Reduced territory",
                "state": "approved",
            }
        )
        result.invalidate_recordset(["effective_target"])
        self.assertEqual(result.original_target, 1000.0)
        self.assertEqual(result.effective_target, 400.0)

    def test_draft_consideration_has_no_effect(self):
        instance = self._gate("cons_draft")
        result = instance.result_ids
        self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": instance.id,
                "requirement_result_id": result.id,
                "consideration_type": "target_adjustment",
                "adjusted_target": 1.0,
                "reason": "Pending approval",
            }
        )
        result.invalidate_recordset(["effective_target"])
        self.assertEqual(result.effective_target, 1000.0)

    def test_latest_approved_adjustment_wins(self):
        instance = self._gate("cons_multi")
        result = instance.result_ids
        Consideration = self.env["sgc.ces.gate.consideration"]
        for value in (800.0, 600.0):
            Consideration.create(
                {
                    "instance_id": instance.id,
                    "requirement_result_id": result.id,
                    "consideration_type": "target_adjustment",
                    "adjusted_target": value,
                    "reason": "Adjusted",
                    "state": "approved",
                }
            )
        result.invalidate_recordset(["effective_target"])
        self.assertEqual(result.effective_target, 600.0)

    def test_approved_consideration_is_immutable(self):
        instance = self._gate("cons_immutable")
        result = instance.result_ids
        consideration = self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": instance.id,
                "requirement_result_id": result.id,
                "consideration_type": "target_adjustment",
                "adjusted_target": 500.0,
                "reason": "Approved",
                "state": "approved",
            }
        )
        with self.assertRaises(UserError):
            consideration.write({"adjusted_target": 999.0})

    def test_revoked_consideration_stops_applying(self):
        instance = self._gate("cons_revoke")
        result = instance.result_ids
        consideration = self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": instance.id,
                "requirement_result_id": result.id,
                "consideration_type": "target_adjustment",
                "adjusted_target": 400.0,
                "reason": "Temporary",
                "state": "approved",
            }
        )
        consideration.action_revoke()
        result.invalidate_recordset(["effective_target"])
        self.assertEqual(result.effective_target, 1000.0)

    def test_extension_wizard_creates_approved_consideration(self):
        instance = self._gate("cons_wizard")
        wizard = self.env["sgc.ces.extension.wizard"].create(
            {
                "instance_id": instance.id,
                "new_due_date": fields.Date.add(instance.due_date, days=10),
                "reason": "Ramp adjustment",
            }
        )
        wizard.action_confirm()
        self.assertTrue(instance.consideration_ids)
        self.assertEqual(instance.consideration_ids.state, "approved")
        self.assertEqual(instance.due_date, instance.consideration_ids.original_due_date)
