# -*- coding: utf-8 -*-
"""Employee to plan binding. Never auto-activated on install."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SgcCesGateAssignment(models.Model):
    _name = "sgc.ces.gate.assignment"
    _description = "SGC CES Gate Assignment"
    _inherit = ["mail.thread"]
    _order = "employee_id, start_date desc"

    employee_id = fields.Many2one("hr.employee", required=True, index=True, tracking=True)
    user_id = fields.Many2one(
        "res.users", related="employee_id.user_id", store=True, index=True, string="User"
    )
    plan_id = fields.Many2one("sgc.ces.gate.plan", required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True, index=True
    )
    state = fields.Selection(
        [
            ("pending_baseline", "Pending Baseline Assessment"),
            ("draft", "Draft"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("closed", "Closed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    baseline_assessment_ids = fields.One2many("sgc.ces.baseline.assessment", "assignment_id")
    baseline_assessment_count = fields.Integer(compute="_compute_baseline_assessment_count")
    start_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="Assignment start. The gate anchor may still be the CES start date.",
    )
    end_date = fields.Date(tracking=True)
    ces_start_date = fields.Date(
        compute="_compute_ces_start_date",
        store=True,
        readonly=False,
        help="Resolved from the plan's start-date strategy; may be overridden manually.",
    )
    manager_user_id = fields.Many2one(
        "res.users", compute="_compute_manager", store=True, readonly=False, string="Reviewer"
    )
    instance_ids = fields.One2many("sgc.ces.gate.instance", "assignment_id")
    instance_count = fields.Integer(compute="_compute_instance_count")
    active = fields.Boolean(default=True)

    _employee_plan_start_uniq = models.Constraint(
        "UNIQUE(employee_id, plan_id, start_date)",
        "This employee already has this plan assigned from that date.",
    )

    @api.depends("employee_id", "plan_id.start_date_strategy")
    def _compute_ces_start_date(self):
        identity = self.env["sgc.ces.identity"]
        for assignment in self:
            strategy = assignment.plan_id.start_date_strategy or "auto"
            assignment.ces_start_date = (
                identity.ces_start_date(assignment.employee_id, strategy)
                if assignment.employee_id
                else False
            )

    @api.depends("employee_id")
    def _compute_manager(self):
        identity = self.env["sgc.ces.identity"]
        for assignment in self:
            manager = identity.resolve_manager(assignment.employee_id)
            assignment.manager_user_id = manager.id if manager else False

    @api.depends("instance_ids")
    def _compute_instance_count(self):
        for assignment in self:
            assignment.instance_count = len(assignment.instance_ids)

    @api.depends("baseline_assessment_ids")
    def _compute_baseline_assessment_count(self):
        for assignment in self:
            assignment.baseline_assessment_count = len(assignment.baseline_assessment_ids)

    @api.depends("employee_id", "plan_id")
    def _compute_display_name(self):
        for assignment in self:
            assignment.display_name = "%s - %s" % (
                assignment.employee_id.name or "",
                assignment.plan_id.display_name or "",
            )

    def action_activate(self):
        for assignment in self:
            if assignment.state == "pending_baseline":
                raise UserError(
                    _(
                        "%s has a pending baseline assessment; complete it before "
                        "activating this assignment so no historical gate is wrongly "
                        "measured from before they had this plan."
                    )
                    % assignment.employee_id.display_name
                )
            if assignment.plan_id.state != "active":
                raise UserError(
                    _("Plan '%s' must be active before an assignment can be activated.")
                    % assignment.plan_id.display_name
                )
            if not assignment.ces_start_date:
                raise UserError(
                    _("No CES start date could be resolved for %s.")
                    % assignment.employee_id.display_name
                )
            assignment.state = "active"
            assignment.generate_instances()
        return True

    def action_suspend(self):
        self.write({"state": "suspended"})
        return True

    def action_close(self):
        self.write({"state": "closed", "end_date": fields.Date.context_today(self)})
        return True

    def action_draft(self):
        self.write({"state": "draft"})
        return True

    def anchor_for_template(self, template, previous_due=None):
        self.ensure_one()
        if template.anchor == "assignment_start":
            return self.start_date
        if template.anchor == "previous_gate_due":
            return previous_due or self.ces_start_date or self.start_date
        return self.ces_start_date or self.start_date

    def generate_instances(self):
        """Idempotently create one gate instance per template. Never duplicates."""
        Instance = self.env["sgc.ces.gate.instance"]
        created = Instance.browse()
        for assignment in self:
            if assignment.state != "active":
                continue
            previous_due = None
            for template in assignment.plan_id.template_ids.sorted(
                key=lambda t: (t.sequence, t.offset_months, t.id)
            ):
                anchor = assignment.anchor_for_template(template, previous_due)
                if not anchor:
                    continue
                _start, _end, due_date, _review = template.compute_schedule(anchor)
                previous_due = due_date
                existing = Instance.search(
                    [
                        ("assignment_id", "=", assignment.id),
                        ("template_id", "=", template.id),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                created |= Instance.create_from_template(assignment, template, anchor)
        return created

    def action_create_baseline_assessment(self):
        """Idempotent: one open baseline assessment per assignment. Requires the
        default review period from ir.config_parameter (default 7 days)."""
        Assessment = self.env["sgc.ces.baseline.assessment"]
        Param = self.env["ir.config_parameter"].sudo()
        due_days = int(Param.get_param("sgc_ces_kpi_banner.baseline_assessment_days", 7))
        created = Assessment.browse()
        for assignment in self:
            existing = assignment.baseline_assessment_ids.filtered(
                lambda a: a.state not in ("completed", "canceled")
            )
            if existing:
                continue
            assignment.state = "pending_baseline"
            record = Assessment.create(
                {
                    "employee_id": assignment.employee_id.id,
                    "assignment_id": assignment.id,
                    "assessment_due_date": fields.Date.add(
                        fields.Date.context_today(self), days=due_days
                    ),
                }
            )
            record.action_refresh_measurements()
            record._create_required_activity()
            created |= record
        return created

    def action_baseline_retrofit(self, reason=None):
        """Cancel any already-overdue gate instances with an explicit auditable
        reason, then create the baseline assessment. Use this instead of
        calling action_cancel() + action_create_baseline_assessment() by hand -
        it's the one path that keeps the retrofit reason on the record."""
        reason = reason or _(
            "Cancelled during baseline-assessment retrofit: this gate was measured "
            "before the employee's baseline was reviewed. See the linked baseline "
            "assessment for the tenure-based context."
        )
        for assignment in self:
            overdue = assignment.instance_ids.filtered(lambda i: i.state == "pending_review")
            if overdue:
                for instance in overdue:
                    instance.message_post(body=reason)
                overdue.action_cancel()
            assignment.state = "pending_baseline"
        return self.action_create_baseline_assessment()

    def action_view_baseline_assessments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Baseline Assessments"),
            "res_model": "sgc.ces.baseline.assessment",
            "view_mode": "list,form",
            "domain": [("assignment_id", "=", self.id)],
            "context": {"default_assignment_id": self.id},
        }

    def action_view_instances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Gate Instances"),
            "res_model": "sgc.ces.gate.instance",
            "view_mode": "list,form",
            "domain": [("assignment_id", "=", self.id)],
            "context": {"default_assignment_id": self.id},
        }
