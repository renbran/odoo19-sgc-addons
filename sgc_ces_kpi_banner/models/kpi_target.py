# -*- coding: utf-8 -*-
"""Daily / monthly KPI target framework.

No target *values* ship with this module. An administrator creates target
records; until they do, the banner's KPI strip simply shows the measured
values with no target and no colour judgement.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .metric_registry import COMPARATOR_SELECTION, METRIC_SELECTION


class SgcCesKpiTarget(models.Model):
    _name = "sgc.ces.kpi.target"
    _description = "SGC CES KPI Target"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True, index=True
    )

    metric_code = fields.Selection(METRIC_SELECTION, required=True)
    comparator = fields.Selection(COMPARATOR_SELECTION, default=">=", required=True)
    target_value = fields.Float(required=True, digits=(16, 2))
    period = fields.Selection(
        [("daily", "Daily"), ("monthly", "Monthly")], default="daily", required=True
    )

    # Applicability, resolved in the same "most specific wins" order as plans.
    job_id = fields.Many2one("hr.job")
    department_id = fields.Many2one("hr.department")
    user_id = fields.Many2one("res.users", string="Specific user")

    # Typed metric parameters reused from the requirement model's vocabulary.
    proposal_only = fields.Boolean()
    min_expected_revenue = fields.Float()
    stale_days = fields.Integer(default=45)
    warn_days = fields.Integer(default=30)
    staleness_field = fields.Selection(
        [
            ("date_last_stage_update", "Last stage change (native, recommended)"),
            ("x_last_activity_date", "Last enrichment run (see help)"),
        ],
        default="date_last_stage_update",
    )
    signature_strategy = fields.Selection(
        [("native", "Native"), ("external", "External"), ("combined", "Either")], default="native"
    )
    qualifying_payment_mode = fields.Selection(
        [
            ("paid", "Fully paid"),
            ("paid_partial", "Fully or partially paid"),
            ("paid_inclusive", "Paid, partial or in payment"),
        ],
        default="paid",
    )
    require_opportunity = fields.Boolean()
    help_text = fields.Text()

    @api.constrains("target_value")
    def _check_target(self):
        for target in self:
            if target.target_value < 0:
                raise ValidationError(_("A KPI target cannot be negative."))

    def metric_params(self):
        self.ensure_one()
        return {
            "proposal_only": self.proposal_only,
            "min_expected_revenue": self.min_expected_revenue,
            "stale_days": self.stale_days,
            "warn_days": self.warn_days,
            "staleness_field": self.staleness_field,
            "signature_strategy": self.signature_strategy,
            "qualifying_payment_mode": self.qualifying_payment_mode,
            "require_opportunity": self.require_opportunity,
        }

    @api.model
    def targets_for_user(self, user, period):
        """Most specific applicable target per metric code."""
        user = user.sudo()
        identity = self.env["sgc.ces.identity"]
        employee = identity._employee_for_user(user)
        version = identity._current_version(employee)
        job = version.job_id if version else self.env["hr.job"].browse()
        department = employee.department_id if employee else self.env["hr.department"].browse()
        pool = self.sudo().search(
            [
                ("period", "=", period),
                ("company_id", "in", user.company_ids.ids or [user.company_id.id]),
            ]
        )

        def applies(target):
            if target.user_id:
                return target.user_id.id == user.id
            if target.department_id:
                return bool(department) and target.department_id.id == department.id
            if target.job_id:
                return bool(job) and target.job_id.id == job.id
            return True

        candidates = pool.filtered(applies)

        def specificity(target):
            if target.user_id:
                return 3
            if target.department_id:
                return 2
            if target.job_id:
                return 1
            return 0

        best = {}
        for target in candidates:
            current = best.get(target.metric_code)
            if not current or specificity(target) > specificity(current):
                best[target.metric_code] = target
        return self.browse([t.id for t in best.values()])
