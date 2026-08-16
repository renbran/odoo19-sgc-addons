# -*- coding: utf-8 -*-
"""Category H - review alerts: idempotency, catch-up, overdue, content rules."""
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestReviews(CesKpiCase):
    def _due_gate(self, days_until_due=7, code="rev"):
        plan = self._make_plan(code=code)
        template = self._make_template(plan, code="g1", review_lead_days=days_until_due)
        self._make_requirement(template)
        plan.action_activate()
        assignment = self._make_assignment(plan)
        instance = assignment.instance_ids
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        # Move the snapshotted schedule so the review is due right now.
        instance.sudo().write(
            {
                "review_date": today,
                "due_date": fields.Date.add(today, days=days_until_due),
            }
        )
        return instance

    def test_cron_creates_exactly_one_review(self):
        instance = self._due_gate(code="rev_one")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.assertEqual(len(instance.review_ids), 1)
        self.assertEqual(instance.state, "pending_review")

    def test_cron_is_idempotent_across_runs(self):
        instance = self._due_gate(code="rev_idem")
        for _ in range(5):
            self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.assertEqual(len(instance.review_ids), 1)

    def test_catch_up_after_downtime(self):
        """A review date that passed while the cron was down still fires once."""
        instance = self._due_gate(code="rev_catchup")
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        instance.sudo().write({"review_date": fields.Date.subtract(today, days=30)})
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.assertEqual(len(instance.review_ids), 1)

    def test_overdue_escalation_is_separate_and_idempotent(self):
        instance = self._due_gate(code="rev_overdue")
        today = fields.Date.context_today(self.env["sgc.ces.identity"])
        instance.sudo().write(
            {
                "review_date": fields.Date.subtract(today, days=10),
                "due_date": fields.Date.subtract(today, days=3),
            }
        )
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        types = instance.review_ids.mapped("alert_type")
        self.assertEqual(sorted(types), ["due_soon", "overdue"])

    def test_review_is_assigned_to_resolved_manager(self):
        instance = self._due_gate(code="rev_mgr")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.assertEqual(instance.review_ids.reviewer_user_id, self.manager_user)

    def test_no_email_is_sent_by_default(self):
        instance = self._due_gate(code="rev_mail")
        domain = [("model", "in", ("sgc.ces.gate.review", "sgc.ces.gate.instance"))]
        before = self.env["mail.mail"].sudo().search_count(domain)
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        self.env.flush_all()
        after = self.env["mail.mail"].sudo().search_count(domain)
        self.assertEqual(before, after)

    def test_activity_is_scheduled_for_the_reviewer(self):
        instance = self._due_gate(code="rev_act")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        activities = self.env["mail.activity"].sudo().search(
            [("res_model", "=", "sgc.ces.gate.review"),
             ("res_id", "=", instance.review_ids.id)]
        )
        self.assertTrue(activities)
        self.assertEqual(activities.user_id, self.manager_user)

    def test_review_body_excludes_sensitive_data(self):
        instance = self._due_gate(code="rev_body")
        body = instance._review_body_text()
        for forbidden in ("invoice", "journal", "payment reference", "salary", "wage"):
            self.assertNotIn(forbidden, body.lower())
        self.assertIn(self.ces_employee.name, body)

    def test_decision_requires_justification(self):
        instance = self._due_gate(code="rev_just")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        review = instance.review_ids
        review.action_start()
        review.decision = "fail"
        with self.assertRaises(UserError):
            review.action_submit()
        review.decision_notes = "Targets not met despite coaching."
        review.action_submit()
        review.action_apply()
        self.assertEqual(instance.state, "failed")

    def test_pass_decision_closes_the_gate(self):
        instance = self._due_gate(code="rev_pass")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        review = instance.review_ids
        review.action_start()
        review.decision = "pass"
        review.action_submit()
        review.action_apply()
        self.assertEqual(instance.state, "passed")
        self.assertTrue(instance.closed_on)

    def test_extend_decision_creates_a_consideration(self):
        instance = self._due_gate(code="rev_extend")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        review = instance.review_ids
        original_due = instance.due_date
        review.action_start()
        review.decision = "extend"
        review.decision_notes = "Onboarding delay."
        review.action_submit()
        review.action_apply()
        self.assertEqual(instance.state, "extended")
        self.assertEqual(instance.due_date, original_due)

    def test_reminder_cron_is_daily_idempotent(self):
        instance = self._due_gate(code="rev_rem")
        self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts()
        Review = self.env["sgc.ces.gate.review"]
        Review._cron_send_review_reminders()
        Review._cron_send_review_reminders()
        self.assertEqual(instance.review_ids.reminder_count, 1)

    def test_cron_batch_is_bounded(self):
        instance = self._due_gate(code="rev_batch")
        created = self.env["sgc.ces.gate.instance"]._cron_process_gate_alerts(batch_size=0)
        self.assertEqual(created, 0)
        self.assertFalse(instance.review_ids)
