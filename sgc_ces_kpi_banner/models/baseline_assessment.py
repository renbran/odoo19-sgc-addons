# -*- coding: utf-8 -*-
"""Existing-employee baseline assessment (MVP).

Gates whether a pre-existing CES employee's gate assignment may move out of
``pending_baseline`` into normal enforcement. Never invents a historical
failure: no gate instance exists (and so no gate can show "failed") until a
manager completes the assessment and the assignment is explicitly activated.

MVP scope: core state machine, tenure-based gate suggestion, 30/60/90-day
measurement snapshot (built entirely from existing metric_registry codes -
no new metric providers), and the four decisions that don't require a
remediation workflow yet. Remediation-period automation, consideration
linkage and configuration_snapshot auditing are deferred.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SgcCesBaselineAssessment(models.Model):
    _name = "sgc.ces.baseline.assessment"
    _description = "SGC CES Baseline Assessment"
    _inherit = ["mail.thread"]
    _order = "ces_start_date asc, id asc"

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one("hr.employee", required=True, index=True, tracking=True)
    user_id = fields.Many2one(
        "res.users", related="employee_id.user_id", store=True, index=True, string="User"
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True, index=True
    )
    manager_user_id = fields.Many2one(
        "res.users", compute="_compute_manager", store=True, readonly=False, string="Manager"
    )
    assignment_id = fields.Many2one(
        "sgc.ces.gate.assignment", required=True, index=True, ondelete="cascade"
    )
    plan_id = fields.Many2one(related="assignment_id.plan_id", store=True, readonly=True)

    ces_start_date = fields.Date(related="assignment_id.ces_start_date", store=True, readonly=True)
    start_date_source = fields.Char(
        compute="_compute_start_date_source",
        help="Which strategy resolved ces_start_date (informational only).",
    )
    tenure_month_at_assessment = fields.Integer(compute="_compute_tenure", store=True)

    suggested_gate_template_id = fields.Many2one(
        "sgc.ces.gate.template", readonly=True,
        help="Tenure-based recommendation only - the manager confirms or overrides it.",
    )
    assigned_gate_template_id = fields.Many2one(
        "sgc.ces.gate.template",
        help="The gate the manager actually assigns. Defaults to the suggestion on confirm.",
    )

    assessment_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    assessment_due_date = fields.Date(required=True, tracking=True)

    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("assigned", "Assigned"),
            ("in_review", "In Review"),
            ("remediation", "Remediation"),
            ("completed", "Completed"),
            ("canceled", "Canceled"),
            ("data_correction_required", "Data Correction Required"),
        ],
        default="pending",
        required=True,
        tracking=True,
        index=True,
    )
    decision = fields.Selection(
        [
            ("confirm_suggested_gate", "Confirm suggested gate"),
            ("assign_different_gate", "Assign a different gate"),
            ("start_remediation", "Start remediation"),
            ("grant_consideration", "Grant a consideration"),
            ("correct_start_date", "Correct start date"),
        ],
        tracking=True,
    )

    # -- measurement snapshot (30/60/90-day windows, existing metrics only) --
    current_pipeline = fields.Float(readonly=True, digits=(16, 2))
    stale_pipeline = fields.Float(
        readonly=True, digits=(16, 2),
        help="Approximated as current_pipeline x stale ratio - no dedicated "
             "monetary stale-pipeline metric exists yet.",
    )
    signed_proposals_30d = fields.Float(readonly=True)
    signed_proposals_60d = fields.Float(readonly=True)
    signed_proposals_90d = fields.Float(readonly=True)
    paid_deals_30d = fields.Float(readonly=True)
    paid_deals_60d = fields.Float(readonly=True)
    paid_deals_90d = fields.Float(readonly=True)

    manager_notes = fields.Text()

    @api.depends("employee_id", "state")
    def _compute_name(self):
        for record in self:
            record.name = _("Baseline assessment: %s") % (record.employee_id.name or "")

    @api.depends("employee_id")
    def _compute_manager(self):
        identity = self.env["sgc.ces.identity"]
        for record in self:
            manager = identity.resolve_manager(record.employee_id)
            record.manager_user_id = manager.id if manager else False

    @api.depends("assignment_id.plan_id")
    def _compute_start_date_source(self):
        for record in self:
            strategy = record.assignment_id.plan_id.start_date_strategy or "auto"
            record.start_date_source = dict(
                record.assignment_id.plan_id._fields["start_date_strategy"].selection
            ).get(strategy, strategy)

    @api.depends("ces_start_date", "assessment_date")
    def _compute_tenure(self):
        for record in self:
            if not record.ces_start_date:
                record.tenure_month_at_assessment = 0
                continue
            reference = record.assessment_date or fields.Date.context_today(record)
            delta = relativedelta(reference, record.ces_start_date)
            record.tenure_month_at_assessment = max(delta.years * 12 + delta.months + 1, 1)

    # ------------------------------------------------------------ suggestion
    def _suggest_template(self):
        """Tenure month 1 -> first gate, 2 -> second, 3+ -> third or later. Recommendation only."""
        self.ensure_one()
        templates = self.assignment_id.plan_id.template_ids.sorted(
            key=lambda t: (t.sequence, t.offset_months, t.id)
        )
        if not templates:
            return self.env["sgc.ces.gate.template"].browse()
        index = min(max(self.tenure_month_at_assessment, 1), len(templates)) - 1
        return templates[index]

    # ----------------------------------------------------------- measurement
    def action_refresh_measurements(self):
        registry = self.env["sgc.ces.metric.registry"]
        for record in self:
            if not record.assignment_id.user_id:
                continue
            user_id = record.assignment_id.user_id.id
            company_ids = record.company_id.ids

            pipeline = registry.safe_evaluate(
                "pipeline_qualified_value",
                {"user_id": user_id, "date_from": None, "date_to": fields.Date.context_today(self),
                 "params": {}, "company_ids": company_ids},
            )
            stale_ratio = registry.safe_evaluate(
                "staleness_stale_ratio",
                {"user_id": user_id, "date_from": None, "date_to": fields.Date.context_today(self),
                 "params": {}, "company_ids": company_ids},
            )
            pipeline_value = pipeline.get("value") or 0.0
            stale_pct = stale_ratio.get("value") or 0.0

            windows = {}
            today = fields.Date.context_today(self)
            for days in (30, 60, 90):
                date_from, date_to = today - relativedelta(days=days), today
                signed = registry.safe_evaluate(
                    "signed_proposal_count",
                    {"user_id": user_id, "date_from": date_from, "date_to": date_to,
                     "params": {}, "company_ids": company_ids},
                )
                paid = registry.safe_evaluate(
                    "paid_deal_count",
                    {"user_id": user_id, "date_from": date_from, "date_to": date_to,
                     "params": {}, "company_ids": company_ids},
                )
                windows[days] = (signed.get("value") or 0.0, paid.get("value") or 0.0)

            record.write(
                {
                    "current_pipeline": pipeline_value,
                    "stale_pipeline": round(pipeline_value * stale_pct / 100.0, 2),
                    "signed_proposals_30d": windows[30][0],
                    "signed_proposals_60d": windows[60][0],
                    "signed_proposals_90d": windows[90][0],
                    "paid_deals_30d": windows[30][1],
                    "paid_deals_60d": windows[60][1],
                    "paid_deals_90d": windows[90][1],
                    "suggested_gate_template_id": record._suggest_template().id,
                }
            )
            if record.state == "pending":
                record.state = "in_review"
        return True

    # -------------------------------------------------------------- decision
    def _apply_decision(self, activate=False):
        """Shared logic. ``activate=False`` is "Apply Decision Only" (leaves
        the assignment in draft); ``activate=True`` is "Apply Decision and
        Activate" (validates start date/gate/manager, then activates in the
        same transaction)."""
        for record in self:
            if record.state in ("completed", "canceled"):
                raise UserError(_("This assessment is already closed."))
            if not record.decision:
                raise UserError(_("Choose a decision before applying it."))

            if record.decision == "correct_start_date":
                if not record.manager_notes:
                    raise UserError(
                        _("Explain the start-date correction in the manager notes before "
                          "recording this decision - the CES start date itself is fixed "
                          "elsewhere (the employee's role-entry date), not on this record.")
                    )
                record.state = "data_correction_required"
                continue

            if record.decision == "confirm_suggested_gate":
                record.assigned_gate_template_id = record.suggested_gate_template_id.id
            elif record.decision == "assign_different_gate" and not record.assigned_gate_template_id:
                raise UserError(_("Choose the gate to assign before confirming this decision."))

            if record.decision == "start_remediation":
                record.state = "remediation"
                continue
            if record.decision == "grant_consideration" and not record.manager_notes:
                raise UserError(_("Record the reason for the consideration in manager notes."))

            if activate:
                if not record.ces_start_date:
                    raise UserError(_("No CES start date resolved - cannot activate."))
                if not record.assigned_gate_template_id:
                    raise UserError(_("No gate assigned - cannot activate."))
                if not record.manager_user_id:
                    raise UserError(_("No manager resolved - cannot activate."))

            record.state = "completed"
            record.assignment_id.write({"state": "draft"})

            if activate:
                record.assignment_id.action_activate()
                record.message_post(
                    body=_("Baseline assessment completed and activated - decision: %s. "
                           "Gate: %s. Prospective gate instances created; no historical "
                           "period was measured or alerted.")
                    % (
                        dict(record._fields["decision"].selection).get(record.decision),
                        record.assigned_gate_template_id.display_name,
                    )
                )
            else:
                record.message_post(
                    body=_("Baseline assessment completed - decision: %s. Gate assignment "
                           "unlocked to draft; activate it to start normal gate enforcement.")
                    % dict(record._fields["decision"].selection).get(record.decision)
                )
        return True

    def action_apply_decision(self):
        """Secondary action: apply the decision, leave the assignment in draft
        for further administrative review before activation."""
        return self._apply_decision(activate=False)

    def action_apply_decision_and_activate(self):
        """Primary action: apply the decision and activate the assignment in
        one confirmed step."""
        return self._apply_decision(activate=True)

    def action_cancel(self):
        self.write({"state": "canceled"})
        return True

    def _create_required_activity(self):
        """One 'CES Baseline Assessment Required' activity per employee,
        assigned to the resolved manager. Idempotent per assessment."""
        Activity = self.env["mail.activity"]
        activity_type = self.env.ref(
            "sgc_ces_kpi_banner.mail_activity_type_ces_gate_review", raise_if_not_found=False
        ) or self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        model_id = self.env["ir.model"]._get_id(self._name)
        for record in self:
            if not record.manager_user_id:
                continue
            existing = Activity.search_count(
                [("res_model", "=", self._name), ("res_id", "=", record.id)]
            )
            if existing:
                continue
            Activity.sudo().create(
                {
                    "res_model_id": model_id,
                    "res_id": record.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "summary": _("CES Baseline Assessment Required - %s") % record.employee_id.name,
                    "user_id": record.manager_user_id.id,
                    "date_deadline": record.assessment_due_date,
                }
            )
