# -*- coding: utf-8 -*-
"""Daily / monthly KPI target framework.

Target *values* are configuration, not code: an administrator or a Team
Leader (for their own team) creates target records here; until one applies
to a user, the banner's KPI strip simply shows the measured value with no
target and no colour judgement. See ``data/kpi_target_data.xml`` for the one
target this module ships out of the box (the daily New-stage-exit quota).
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
    weekdays_only = fields.Boolean(
        string="Weekdays only",
        help="Only evaluated Monday-Friday. On Saturday and Sunday this target "
        "is left out of the banner entirely instead of showing a false shortfall.",
    )

    # Applicability, resolved in the same "most specific wins" order as plans.
    job_id = fields.Many2one("hr.job")
    department_id = fields.Many2one("hr.department")
    team_id = fields.Many2one(
        "crm.team",
        string="Sales Team",
        help="Restrict this target to one sales team's members. A CES KPI "
        "Manager who leads a team may only create/edit targets that carry "
        "their own team here.",
    )
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

    @api.constrains("team_id", "user_id")
    def _check_team_scope(self):
        for target in self:
            if not (target.team_id and target.user_id):
                continue
            members = target.team_id.member_ids
            if target.user_id != target.team_id.user_id and target.user_id not in members:
                raise ValidationError(
                    _("%(user)s is not a member (or the leader) of the %(team)s sales team.")
                    % {"user": target.user_id.name, "team": target.team_id.name}
                )

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
    def targets_for_user(self, user, period, reference=None):
        """Most specific applicable target per metric code.

        Specificity order (highest wins): specific user > sales team >
        department > job > everyone. A ``weekdays_only`` target is dropped
        entirely on Saturday/Sunday so the banner never shows a false
        shortfall on a day the target does not apply. ``reference`` overrides
        "today" for deterministic tests; production callers leave it unset.
        """
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
        today = fields.Date.to_date(reference) if reference else fields.Date.context_today(self)
        if today.weekday() >= 5:
            pool = pool.filtered(lambda t: not t.weekdays_only)

        def applies(target):
            if target.user_id:
                return target.user_id.id == user.id
            if target.team_id:
                return user.id in target.team_id.member_ids.ids or user.id == target.team_id.user_id.id
            if target.department_id:
                return bool(department) and target.department_id.id == department.id
            if target.job_id:
                return bool(job) and target.job_id.id == job.id
            return True

        candidates = pool.filtered(applies)

        def specificity(target):
            if target.user_id:
                return 4
            if target.team_id:
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
