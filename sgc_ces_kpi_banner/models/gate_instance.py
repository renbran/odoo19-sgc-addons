# -*- coding: utf-8 -*-
"""Gate instance - one snapshotted gate occurrence for one employee.

At creation time every scheduling and policy value is copied off the template
and every requirement definition is copied into a
``sgc.ces.gate.requirement.result`` row.  Later edits to the plan (which are
only possible by creating a new plan version) therefore cannot rewrite
history.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .metric_registry import compare, progress_ratio

_logger = logging.getLogger(__name__)

STATUS_ON_TRACK = "on_track"
STATUS_AT_RISK = "at_risk"
STATUS_OFF_TRACK = "off_track"


class SgcCesGateInstance(models.Model):
    _name = "sgc.ces.gate.instance"
    _description = "SGC CES Gate Instance"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date asc, id asc"

    name = fields.Char(required=True, readonly=True)
    assignment_id = fields.Many2one(
        "sgc.ces.gate.assignment", required=True, ondelete="cascade", index=True, readonly=True
    )
    template_id = fields.Many2one("sgc.ces.gate.template", required=True, readonly=True, index=True)
    plan_id = fields.Many2one(
        "sgc.ces.gate.plan", related="assignment_id.plan_id", store=True, index=True
    )
    employee_id = fields.Many2one(
        "hr.employee", related="assignment_id.employee_id", store=True, index=True
    )
    user_id = fields.Many2one(
        "res.users", related="assignment_id.user_id", store=True, index=True
    )
    manager_user_id = fields.Many2one(
        "res.users", related="assignment_id.manager_user_id", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company", related="assignment_id.company_id", store=True, index=True
    )

    # -- snapshotted schedule (never recomputed) -----------------------------
    anchor_date = fields.Date(required=True, readonly=True)
    period_start = fields.Date(required=True, readonly=True, index=True)
    period_end = fields.Date(required=True, readonly=True)
    due_date = fields.Date(required=True, readonly=True, index=True)
    review_date = fields.Date(required=True, readonly=True, index=True)
    grace_days = fields.Integer(readonly=True)
    review_lead_days = fields.Integer(readonly=True)
    pass_threshold = fields.Float(readonly=True)
    outcome_policy = fields.Selection(
        [("informational", "Informational only"), ("review_required", "Manager review required")],
        readonly=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "In Progress"),
            ("pending_review", "Pending Review"),
            ("in_review", "In Review"),
            ("passed", "Passed"),
            ("failed", "Not Met"),
            ("extended", "Extended"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    closed_on = fields.Datetime(readonly=True)
    closed_by_id = fields.Many2one("res.users", readonly=True)

    result_ids = fields.One2many("sgc.ces.gate.requirement.result", "instance_id")
    review_ids = fields.One2many("sgc.ces.gate.review", "instance_id")
    consideration_ids = fields.One2many("sgc.ces.gate.consideration", "instance_id")

    # -- live computed progress ---------------------------------------------
    score = fields.Float(compute="_compute_progress", string="Weighted score (%)")
    mandatory_met = fields.Boolean(compute="_compute_progress")
    projected_outcome = fields.Selection(
        [("pass", "Would pass"), ("fail", "Would not pass")], compute="_compute_progress"
    )
    health = fields.Selection(
        [
            (STATUS_ON_TRACK, "On track"),
            (STATUS_AT_RISK, "At risk"),
            (STATUS_OFF_TRACK, "Off track"),
        ],
        compute="_compute_progress",
    )
    days_remaining = fields.Integer(compute="_compute_days_remaining")

    _assignment_template_uniq = models.Constraint(
        "UNIQUE(assignment_id, template_id)",
        "A gate instance already exists for this assignment and template.",
    )

    # ------------------------------------------------------------------ setup
    @api.model
    def create_from_template(self, assignment, template, anchor_date):
        period_start, period_end, due_date, review_date = template.compute_schedule(anchor_date)
        instance = self.create(
            {
                "name": template.name,
                "assignment_id": assignment.id,
                "template_id": template.id,
                "anchor_date": anchor_date,
                "period_start": period_start,
                "period_end": period_end,
                "due_date": due_date,
                "review_date": review_date,
                "grace_days": template.grace_days,
                "review_lead_days": template.review_lead_days,
                "pass_threshold": template.pass_threshold,
                "outcome_policy": template.outcome_policy,
                "state": "active",
            }
        )
        Result = self.env["sgc.ces.gate.requirement.result"]
        for requirement in template.requirement_ids.sorted(key=lambda r: (r.sequence, r.id)):
            Result.create(
                {
                    "instance_id": instance.id,
                    "requirement_id": requirement.id,
                    "name": requirement.name,
                    "metric_code": requirement.metric_code,
                    "comparator": requirement.comparator,
                    "original_target": requirement.target_value,
                    "measurement_window": requirement.measurement_window,
                    "level": requirement.level,
                    "weight": requirement.weight,
                    "sequence": requirement.sequence,
                    "help_text": requirement.help_text,
                    "params_json": json.dumps(requirement.metric_params(), sort_keys=True),
                }
            )
        return instance

    # ------------------------------------------------------------- computed
    @api.depends("due_date")
    def _compute_days_remaining(self):
        today = fields.Date.context_today(self)
        for instance in self:
            instance.days_remaining = (
                (instance.due_date - today).days if instance.due_date else 0
            )

    @api.depends("result_ids", "result_ids.achieved", "result_ids.weight", "pass_threshold")
    def _compute_progress(self):
        for instance in self:
            instance.score = instance._weighted_score()
            instance.mandatory_met = instance._mandatory_met()
            passes = instance.mandatory_met and instance.score >= (instance.pass_threshold or 0.0)
            instance.projected_outcome = "pass" if passes else "fail"
            instance.health = instance._health()

    def _weighted_score(self):
        """Weighted completion percentage across weighted + mandatory results.

        Informational requirements never move the score.
        """
        self.ensure_one()
        scored = self.result_ids.filtered(lambda r: r.level in ("mandatory", "weighted"))
        if not scored:
            return 100.0
        total_weight = sum(max(r.weight, 0.0) or 1.0 for r in scored)
        if total_weight <= 0:
            return 0.0
        acquired = sum((max(r.weight, 0.0) or 1.0) * r.progress for r in scored)
        return round(acquired / total_weight * 100.0, 2)

    def _mandatory_met(self):
        """A single unmet mandatory requirement can never be averaged away."""
        self.ensure_one()
        mandatory = self.result_ids.filtered(lambda r: r.level == "mandatory")
        return all(r.achieved for r in mandatory)

    def _health(self):
        self.ensure_one()
        if self.state == "passed":
            return STATUS_ON_TRACK
        if self.state in ("failed",):
            return STATUS_OFF_TRACK
        if self.mandatory_met and self.score >= (self.pass_threshold or 0.0):
            return STATUS_ON_TRACK
        remaining = self.days_remaining
        if remaining is None:
            return STATUS_AT_RISK
        if remaining < 0:
            return STATUS_OFF_TRACK
        # Expected linear progress across the measurement period.
        if self.period_start and self.due_date and self.due_date > self.period_start:
            total = (self.due_date - self.period_start).days or 1
            elapsed = max(total - remaining, 0)
            expected = elapsed / total * 100.0
        else:
            expected = 0.0
        if self.score + 10.0 >= expected:
            return STATUS_ON_TRACK
        if self.score + 30.0 >= expected:
            return STATUS_AT_RISK
        return STATUS_OFF_TRACK

    # ------------------------------------------------------------ evaluation
    def evaluate(self):
        """Re-measure every requirement result of these instances."""
        for instance in self:
            for result in instance.result_ids:
                result.evaluate()
        self.invalidate_recordset(["score", "mandatory_met", "projected_outcome", "health"])
        return True

    # ------------------------------------------------------------- workflow
    def action_evaluate(self):
        self.evaluate()
        return True

    def action_open_review(self):
        self.ensure_one()
        review = self.review_ids.filtered(lambda r: r.state not in ("done", "cancelled"))[:1]
        if not review:
            review = self.env["sgc.ces.gate.review"].create_for_instance(self, reason="manual")
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.ces.gate.review",
            "res_id": review.id,
            "view_mode": "form",
            "target": "current",
        }

    def _close(self, state):
        self.write(
            {
                "state": state,
                "closed_on": fields.Datetime.now(),
                "closed_by_id": self.env.uid,
            }
        )

    def action_mark_passed(self):
        self._close("passed")
        return True

    def action_mark_failed(self):
        self._close("failed")
        return True

    def action_cancel(self):
        for instance in self:
            if instance.state in ("passed", "failed"):
                raise UserError(_("A closed gate cannot be cancelled."))
        self.write({"state": "cancelled"})
        return True

    # -------------------------------------------------- considerations view
    def effective_due_date(self):
        """Original due date plus any approved extension. Never rewrites the field."""
        self.ensure_one()
        extensions = self.consideration_ids.filtered(
            lambda c: c.state == "approved" and c.consideration_type == "extension"
        )
        if not extensions:
            return self.due_date
        return max(extensions.mapped("new_due_date") + [self.due_date])

    # -------------------------------------------------------------- summary
    def summary_dict(self):
        """Serialisable summary, safe for the banner (no accounting details)."""
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": dict(self._fields["state"].selection).get(self.state),
            "due_date": fields.Date.to_string(self.due_date),
            "effective_due_date": fields.Date.to_string(self.effective_due_date()),
            "period_start": fields.Date.to_string(self.period_start),
            "days_remaining": self.days_remaining,
            "score": self.score,
            "pass_threshold": self.pass_threshold,
            "mandatory_met": self.mandatory_met,
            "health": self.health,
            "requirements": [r.summary_dict() for r in self.result_ids.sorted(
                key=lambda r: (r.sequence, r.id))],
        }

    def _review_body_text(self):
        """Reviewer-facing body.

        Deliberately contains no customer name, deal name, invoice number,
        payment reference or contract/salary data - only the employee, the
        gate schedule and the aggregate requirement figures.
        """
        self.ensure_one()
        lines = [
            _("Gate: %s") % self.name,
            _("Specialist: %s") % (self.employee_id.name or ""),
            _("Due: %s") % (fields.Date.to_string(self.effective_due_date()) or ""),
            _("Days remaining: %s") % self.days_remaining,
            _("Weighted score: %.1f%% (threshold %.1f%%)") % (self.score, self.pass_threshold or 0.0),
            _("Mandatory requirements met: %s") % (_("yes") if self.mandatory_met else _("no")),
            "",
            _("Requirements:"),
        ]
        for result in self.result_ids.sorted(key=lambda r: (r.sequence, r.id)):
            lines.append(
                "- %s: %s %s %s (current %s) [%s]"
                % (
                    result.name,
                    dict(result._fields["comparator"].selection).get(result.comparator, ""),
                    result.effective_target,
                    dict(result._fields["level"].selection).get(result.level, ""),
                    result.measured_value,
                    _("met") if result.achieved else _("not met"),
                )
            )
        return "<br/>".join(lines)

    # -------------------------------------------------------- cron helpers
    @api.model
    def _cron_process_gate_alerts(self, batch_size=200):
        """Hourly, idempotent, bounded, per-record isolated.

        Creates at most one review per (instance, alert type, scheduled date).
        Catch-up safe: an instance whose review date has already passed but has
        no review yet still gets exactly one review created.
        """
        batch_size = max(int(batch_size or 0), 0)
        if not batch_size:
            return 0
        Review = self.env["sgc.ces.gate.review"]
        today = fields.Date.context_today(self)
        candidates = self.search(
            [
                ("state", "in", ("active", "pending_review")),
                ("review_date", "<=", today),
                ("outcome_policy", "=", "review_required"),
            ],
            order="review_date asc, id asc",
            limit=batch_size,
        )
        created = 0
        for instance in candidates:
            try:
                existing = Review.search_count(
                    [
                        ("instance_id", "=", instance.id),
                        ("alert_type", "=", "due_soon"),
                        ("alert_scheduled_date", "=", instance.review_date),
                    ]
                )
                if existing:
                    if instance.state == "active":
                        instance.state = "pending_review"
                    continue
                instance.evaluate()
                Review.create_for_instance(instance, reason="due_soon")
                instance.state = "pending_review"
                created += 1
            except Exception:  # noqa: BLE001 - one bad record must not stop the batch
                _logger.exception(
                    "sgc_ces_kpi_banner: gate alert failed for instance %s", instance.id
                )
                self.env.cr.rollback()
        # Overdue escalation, same idempotency contract.
        overdue = self.search(
            [
                ("state", "in", ("pending_review", "in_review")),
                ("due_date", "<", today),
            ],
            limit=batch_size,
        )
        for instance in overdue:
            try:
                if instance.effective_due_date() >= today:
                    continue
                existing = Review.search_count(
                    [
                        ("instance_id", "=", instance.id),
                        ("alert_type", "=", "overdue"),
                        ("alert_scheduled_date", "=", instance.due_date),
                    ]
                )
                if existing:
                    continue
                Review.create_for_instance(instance, reason="overdue")
                created += 1
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "sgc_ces_kpi_banner: overdue escalation failed for instance %s", instance.id
                )
                self.env.cr.rollback()
        return created
