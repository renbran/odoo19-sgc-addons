# -*- coding: utf-8 -*-
"""Guided CES KPI setup wizard.

Seventeen ordered steps, each a page of the same transient record so the
administrator can move back and forth before anything is written.  Nothing is
persisted until ``action_apply`` runs, and even then **no assignment is ever
activated automatically** - the wizard creates them in ``draft``.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

STEPS = [
    ("step_1_intro", "1. Introduction"),
    ("step_2_identity", "2. Identify the CES role"),
    ("step_3_stages", "3. Map the CRM stages"),
    ("step_4_plan", "4. Name the gate plan"),
    ("step_5_anchor", "5. Choose the start-date strategy"),
    ("step_6_gate1", "6. Gate 1 schedule"),
    ("step_7_gate1_req", "7. Gate 1 requirement"),
    ("step_8_gate2", "8. Gate 2 schedule"),
    ("step_9_gate2_req", "9. Gate 2 requirement"),
    ("step_10_gate3", "10. Gate 3 schedule"),
    ("step_11_gate3_req", "11. Gate 3 requirement"),
    ("step_12_staleness", "12. Staleness policy"),
    ("step_13_signature", "13. Signature source"),
    ("step_14_payment", "14. Payment qualification"),
    ("step_15_review", "15. Review and alerting"),
    ("step_16_assignments", "16. Employees to enrol"),
    ("step_17_summary", "17. Review and apply"),
]


class SgcCesSetupWizard(models.TransientModel):
    _name = "sgc.ces.setup.wizard"
    _description = "SGC CES Setup Wizard"

    step = fields.Selection(STEPS, default="step_1_intro", required=True)
    step_index = fields.Integer(compute="_compute_step_index")

    # 2 - identity
    job_id = fields.Many2one("hr.job", string="CES job position")
    job_name = fields.Char(string="CES job title", default="Telesales/Client Engagement Specialist")
    # 3 - stages
    proposal_stage_id = fields.Many2one("crm.stage", string="Proposal stage")
    won_stage_id = fields.Many2one("crm.stage", string="Won stage")
    excluded_stage_ids = fields.Many2many("crm.stage", string="Stages that are not live pipeline")
    # 4 - plan
    plan_name = fields.Char(default="CES Ramp Plan", required=True)
    plan_code = fields.Char(default="ces_ramp", required=True)
    plan_description = fields.Text()
    # 5 - anchor
    start_date_strategy = fields.Selection(
        [
            ("auto", "Automatic"),
            ("role_entry", "CES role entry date"),
            ("contract_start", "Contract start date"),
            ("create_date", "Employee creation date"),
        ],
        default="auto",
        required=True,
    )
    # 6/7 - gate 1
    gate1_name = fields.Char(default="Gate 1 - Build the pipeline")
    gate1_offset = fields.Integer(default=0)
    gate1_duration = fields.Integer(default=1)
    gate1_target = fields.Float(string="Qualified pipeline target", default=0.0)
    # 8/9 - gate 2
    gate2_name = fields.Char(default="Gate 2 - Convert to proposals")
    gate2_offset = fields.Integer(default=1)
    gate2_duration = fields.Integer(default=1)
    gate2_target = fields.Float(string="Signed proposal target", default=0.0)
    # 10/11 - gate 3
    gate3_name = fields.Char(default="Gate 3 - Close and collect")
    gate3_offset = fields.Integer(default=2)
    gate3_duration = fields.Integer(default=1)
    gate3_target = fields.Float(string="Paid deal target", default=0.0)
    # 12 - staleness
    staleness_field = fields.Selection(
        [
            ("date_last_stage_update", "Last stage change (native, recommended)"),
            ("x_last_activity_date", "Last enrichment run (caveat: enrichment only)"),
        ],
        default="date_last_stage_update",
        required=True,
    )
    stale_days = fields.Integer(default=45)
    warn_days = fields.Integer(default=30)
    stale_ceiling = fields.Float(
        string="Maximum stale ratio (%)", default=0.0,
        help="Leave at 0 to skip the staleness requirement entirely."
    )
    # 13 - signature
    signature_strategy = fields.Selection(
        [("native", "Native Odoo signature"), ("external", "External envelope fields"),
         ("combined", "Either")],
        default="native",
        required=True,
    )
    # 14 - payment
    qualifying_payment_mode = fields.Selection(
        [("paid", "Fully paid"), ("paid_partial", "Fully or partially paid"),
         ("paid_inclusive", "Paid, partial or in payment")],
        default="paid",
        required=True,
    )
    require_opportunity = fields.Boolean(default=False)
    # 15 - review
    review_lead_days = fields.Integer(default=7, required=True)
    outcome_policy = fields.Selection(
        [("informational", "Informational only"), ("review_required", "Manager review required")],
        default="review_required",
        required=True,
    )
    review_email_enabled = fields.Boolean(default=False)
    # 16 - assignments
    employee_ids = fields.Many2many("hr.employee", string="Enrol these specialists")
    # 17 - summary
    summary = fields.Text(readonly=True)
    created_plan_id = fields.Many2one("sgc.ces.gate.plan", readonly=True)

    @api.depends("step")
    def _compute_step_index(self):
        order = [code for code, _label in STEPS]
        for wizard in self:
            wizard.step_index = order.index(wizard.step) + 1 if wizard.step in order else 1

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        identity = self.env["sgc.ces.identity"]
        job = identity._resolve_ces_job()
        if job and "job_id" in fields_list:
            values["job_id"] = job.id
        proposal = identity.proposal_stage()
        if proposal and "proposal_stage_id" in fields_list:
            values["proposal_stage_id"] = proposal.id
        won = identity.won_stage()
        if won and "won_stage_id" in fields_list:
            values["won_stage_id"] = won.id
        excluded = identity.excluded_stage_ids()
        if excluded and "excluded_stage_ids" in fields_list:
            values["excluded_stage_ids"] = [(6, 0, excluded)]
        if job and "employee_ids" in fields_list:
            values["employee_ids"] = [(6, 0, identity.ces_employees().ids)]
        return values

    # ----------------------------------------------------------- navigation
    def _reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_next(self):
        self.ensure_one()
        order = [code for code, _label in STEPS]
        index = order.index(self.step)
        if index + 1 < len(order):
            self.step = order[index + 1]
        if self.step == "step_17_summary":
            self.summary = self._build_summary()
        return self._reopen()

    def action_previous(self):
        self.ensure_one()
        order = [code for code, _label in STEPS]
        index = order.index(self.step)
        if index > 0:
            self.step = order[index - 1]
        return self._reopen()

    def _build_summary(self):
        self.ensure_one()
        lines = [
            _("Plan: %s (%s)") % (self.plan_name, self.plan_code),
            _("Start-date strategy: %s") % self.start_date_strategy,
            _("Gates: %s / %s / %s") % (self.gate1_name, self.gate2_name, self.gate3_name),
            _("Staleness source: %s (stale after %s days)") % (self.staleness_field, self.stale_days),
            _("Signature strategy: %s") % self.signature_strategy,
            _("Payment qualification: %s") % self.qualifying_payment_mode,
            _("Review lead time: %s days") % self.review_lead_days,
            _("Employees to enrol: %s (created as DRAFT, not activated)") % len(self.employee_ids),
        ]
        if not (self.gate1_target or self.gate2_target or self.gate3_target):
            lines.append(
                _("WARNING: every gate target is still zero. No target values are shipped "
                  "with this module; enter the numbers your business actually uses.")
            )
        return "\n".join(lines)

    # ---------------------------------------------------------------- apply
    def action_apply(self):
        self.ensure_one()
        if self.created_plan_id:
            raise UserError(_("This wizard has already been applied."))
        Param = self.env["ir.config_parameter"].sudo()
        if self.job_id:
            Param.set_param("sgc_ces_kpi_banner.ces_job_id", str(self.job_id.id))
        if self.job_name:
            Param.set_param("sgc_ces_kpi_banner.ces_job_name", self.job_name)
        if self.proposal_stage_id:
            Param.set_param("sgc_ces_kpi_banner.proposal_stage_id", str(self.proposal_stage_id.id))
        if self.won_stage_id:
            Param.set_param("sgc_ces_kpi_banner.won_stage_id", str(self.won_stage_id.id))
        if self.excluded_stage_ids:
            Param.set_param(
                "sgc_ces_kpi_banner.excluded_stage_ids",
                ",".join(str(s) for s in self.excluded_stage_ids.ids),
            )
        Param.set_param(
            "sgc_ces_kpi_banner.review_email_enabled", "True" if self.review_email_enabled else "False"
        )

        plan = self.env["sgc.ces.gate.plan"].create(
            {
                "name": self.plan_name,
                "code": self.plan_code,
                "description": self.plan_description,
                "start_date_strategy": self.start_date_strategy,
                "job_id": self.job_id.id if self.job_id else False,
                "is_default": True,
            }
        )
        self._create_gate(plan, 1, self.gate1_name, self.gate1_offset, self.gate1_duration,
                          "pipeline_qualified_value", self.gate1_target)
        self._create_gate(plan, 2, self.gate2_name, self.gate2_offset, self.gate2_duration,
                          "signed_proposal_count", self.gate2_target)
        self._create_gate(plan, 3, self.gate3_name, self.gate3_offset, self.gate3_duration,
                          "paid_deal_count", self.gate3_target)
        plan.action_activate()

        Assignment = self.env["sgc.ces.gate.assignment"]
        for employee in self.employee_ids:
            if Assignment.search_count(
                [("employee_id", "=", employee.id), ("plan_id", "=", plan.id)]
            ):
                continue
            # Deliberately left in draft: an administrator must activate it.
            Assignment.create(
                {
                    "employee_id": employee.id,
                    "plan_id": plan.id,
                    "state": "draft",
                    "start_date": fields.Date.context_today(self),
                }
            )
        self.created_plan_id = plan.id
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.ces.gate.plan",
            "res_id": plan.id,
            "view_mode": "form",
            "target": "current",
        }

    def _create_gate(self, plan, number, name, offset, duration, metric_code, target):
        template = self.env["sgc.ces.gate.template"].create(
            {
                "plan_id": plan.id,
                "name": name or _("Gate %s") % number,
                "code": "gate_%s" % number,
                "sequence": number * 10,
                "offset_months": offset,
                "duration_months": max(duration, 1),
                "anchor": "ces_start",
                "review_lead_days": self.review_lead_days,
                "outcome_policy": self.outcome_policy,
            }
        )
        Requirement = self.env["sgc.ces.gate.requirement"]
        Requirement.create(
            {
                "template_id": template.id,
                "name": name or _("Gate %s target") % number,
                "metric_code": metric_code,
                "comparator": ">=",
                "target_value": target,
                "measurement_window": "since_gate_start",
                "level": "mandatory",
                "signature_strategy": self.signature_strategy,
                "qualifying_payment_mode": self.qualifying_payment_mode,
                "require_opportunity": self.require_opportunity,
                "staleness_field": self.staleness_field,
                "stale_days": self.stale_days,
                "warn_days": self.warn_days,
            }
        )
        if self.stale_ceiling > 0:
            Requirement.create(
                {
                    "template_id": template.id,
                    "name": _("Pipeline hygiene"),
                    "metric_code": "staleness_stale_ratio",
                    "comparator": "<=",
                    "target_value": self.stale_ceiling,
                    "measurement_window": "all_time",
                    "level": "weighted",
                    "weight": 1.0,
                    "staleness_field": self.staleness_field,
                    "stale_days": self.stale_days,
                    "warn_days": self.warn_days,
                }
            )
        return template
