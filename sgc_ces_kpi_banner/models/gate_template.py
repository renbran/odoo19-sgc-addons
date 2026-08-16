# -*- coding: utf-8 -*-
"""Gate template - schedule and policy for one gate inside a plan.

Scheduling formula (see README for worked examples)::

    period_start = anchor + relativedelta(months=offset_months)
    period_end   = anchor + relativedelta(months=offset_months + duration_months)
    due_date     = period_end  (or end of that calendar month)
    due_date     = working_day_adjust(due_date)
    review_date  = due_date - review_lead_days

``relativedelta`` clamps day overflow, so an anchor of 31 January plus one
month is 28 February (29 February in a leap year) rather than 3 March.
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SgcCesGateTemplate(models.Model):
    _name = "sgc.ces.gate.template"
    _description = "SGC CES Gate Template"
    _order = "plan_id, sequence, offset_months"

    name = fields.Char(required=True)
    code = fields.Char(required=True, help="Stable identifier, unique within the plan.")
    plan_id = fields.Many2one(
        "sgc.ces.gate.plan", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="plan_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    description = fields.Text()

    offset_months = fields.Integer(
        string="Starts after (months)",
        default=0,
        required=True,
        help="Months from the anchor date to the start of this gate's measurement period.",
    )
    duration_months = fields.Integer(
        string="Duration (months)",
        default=1,
        required=True,
        help="Length of the measurement period. The gate is due at the end of it.",
    )
    anchor = fields.Selection(
        [
            ("ces_start", "CES start date"),
            ("assignment_start", "Assignment start date"),
            ("previous_gate_due", "Previous gate due date"),
        ],
        default="ces_start",
        required=True,
    )
    due_day_policy = fields.Selection(
        [
            ("same_day", "Same day of month as the anchor"),
            ("end_of_month", "Last day of the month"),
        ],
        default="same_day",
        required=True,
    )
    working_day_adjustment = fields.Selection(
        [
            ("none", "No adjustment"),
            ("next", "Move to next working day"),
            ("previous", "Move to previous working day"),
        ],
        default="none",
        required=True,
        help="Working days are Monday-Friday. Public holidays are not modelled.",
    )
    review_lead_days = fields.Integer(
        default=7,
        required=True,
        help="How many days before the due date the manager review alert is raised.",
    )
    grace_days = fields.Integer(
        default=0,
        help="Days after the due date during which the gate is still evaluated before failing.",
    )
    outcome_policy = fields.Selection(
        [
            ("informational", "Informational only"),
            ("review_required", "Manager review required"),
        ],
        default="review_required",
        required=True,
        help="v1 never blocks any CRM operation regardless of this setting.",
    )
    pass_threshold = fields.Float(
        default=100.0,
        help="Weighted score (%) required to pass, once every mandatory requirement is met.",
    )
    requirement_ids = fields.One2many(
        "sgc.ces.gate.requirement", "template_id", copy=True
    )
    requirement_count = fields.Integer(compute="_compute_requirement_count")
    active = fields.Boolean(default=True)

    _code_plan_uniq = models.Constraint(
        "UNIQUE(code, plan_id)",
        "Gate template codes must be unique inside a plan.",
    )

    @api.depends("requirement_ids")
    def _compute_requirement_count(self):
        for template in self:
            template.requirement_count = len(template.requirement_ids)

    @api.depends("name", "plan_id.name")
    def _compute_display_name(self):
        for template in self:
            template.display_name = "%s / %s" % (template.plan_id.display_name or "", template.name or "")

    @api.constrains("offset_months", "duration_months", "review_lead_days", "grace_days")
    def _check_schedule(self):
        for template in self:
            if template.offset_months < 0:
                raise ValidationError(_("The month offset cannot be negative."))
            if template.duration_months < 1:
                raise ValidationError(_("Gate duration must be at least one month."))
            if template.review_lead_days < 0:
                raise ValidationError(_("Review lead days cannot be negative."))
            if template.grace_days < 0:
                raise ValidationError(_("Grace days cannot be negative."))

    @api.constrains("pass_threshold")
    def _check_threshold(self):
        for template in self:
            if not 0.0 <= template.pass_threshold <= 100.0:
                raise ValidationError(_("The pass threshold must be between 0 and 100."))

    # -- scheduling ----------------------------------------------------------
    @staticmethod
    def _end_of_month(value):
        return value + relativedelta(day=31)

    @staticmethod
    def _adjust_working_day(value, mode):
        if mode == "none":
            return value
        step = 1 if mode == "next" else -1
        guard = 0
        while value.weekday() >= 5 and guard < 10:
            value = value + timedelta(days=step)
            guard += 1
        return value

    def compute_schedule(self, anchor_date):
        """Return ``(period_start, period_end, due_date, review_date)``."""
        self.ensure_one()
        anchor_date = fields.Date.to_date(anchor_date)
        if not anchor_date:
            return False, False, False, False
        period_start = anchor_date + relativedelta(months=self.offset_months)
        period_end = anchor_date + relativedelta(
            months=self.offset_months + self.duration_months
        )
        due_date = period_end
        if self.due_day_policy == "end_of_month":
            due_date = self._end_of_month(due_date)
        due_date = self._adjust_working_day(due_date, self.working_day_adjustment)
        review_date = due_date - timedelta(days=self.review_lead_days)
        return period_start, period_end, due_date, review_date
