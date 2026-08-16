# -*- coding: utf-8 -*-
"""Versioned gate plan - the root configuration record."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

LOCKED_FIELDS = {
    "code",
    "version",
    "state",
}


class SgcCesGatePlan(models.Model):
    _name = "sgc.ces.gate.plan"
    _description = "SGC CES Gate Plan (versioned)"
    _inherit = ["mail.thread"]
    _order = "code asc, version desc"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        required=True,
        tracking=True,
        help="Stable identifier shared by every version of this plan.",
    )
    version = fields.Integer(default=1, required=True, tracking=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("superseded", "Superseded"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True, index=True
    )
    description = fields.Text()

    # -- single default plan --------------------------------------------------
    # No routing: exactly one active plan per company applies to every CES
    # employee. Use action_new_version() to change it, not a second plan.
    is_default = fields.Boolean(
        string="Default plan",
        default=True,
        help="Every CES employee uses the one active default plan for their company.",
    )

    start_date_strategy = fields.Selection(
        [
            ("auto", "Automatic (role entry, then contract start, then employee creation)"),
            ("role_entry", "CES role entry date"),
            ("contract_start", "Contract start date"),
            ("create_date", "Employee record creation date"),
        ],
        default="auto",
        required=True,
        help="How the CES start date - the anchor for gate scheduling - is derived.",
    )

    template_ids = fields.One2many(
        "sgc.ces.gate.template", "plan_id", string="Gate Templates", copy=True
    )
    assignment_ids = fields.One2many("sgc.ces.gate.assignment", "plan_id", string="Assignments")
    template_count = fields.Integer(compute="_compute_counts")
    assignment_count = fields.Integer(compute="_compute_counts")
    predecessor_id = fields.Many2one("sgc.ces.gate.plan", string="Previous Version", readonly=True)

    _code_version_company_uniq = models.Constraint(
        "UNIQUE(code, version, company_id)",
        "A gate plan version must be unique per company.",
    )

    @api.depends("template_ids", "assignment_ids")
    def _compute_counts(self):
        for plan in self:
            plan.template_count = len(plan.template_ids)
            plan.assignment_count = len(plan.assignment_ids)

    @api.constrains("version")
    def _check_version(self):
        for plan in self:
            if plan.version < 1:
                raise ValidationError(_("Plan version must be 1 or greater."))

    @api.depends("name", "version")
    def _compute_display_name(self):
        for plan in self:
            plan.display_name = "%s (v%s)" % (plan.name or "", plan.version)

    # -- versioning guard ----------------------------------------------------
    def _is_locked(self):
        self.ensure_one()
        return self.state in ("active", "superseded") and bool(self.assignment_ids)

    def write(self, vals):
        protected = set(vals) - {"state", "active", "name", "description", "sequence"}
        if protected:
            for plan in self:
                if plan._is_locked():
                    raise UserError(
                        _(
                            "Plan '%s' (v%s) is active and already assigned; its rules are "
                            "frozen so historical gate instances stay reproducible.\n"
                            "Use 'New Version' to change it."
                        )
                        % (plan.name, plan.version)
                    )
        return super().write(vals)

    def unlink(self):
        for plan in self:
            if plan.assignment_ids:
                raise UserError(
                    _("Plan '%s' has assignments and cannot be deleted; archive it instead.")
                    % plan.display_name
                )
        return super().unlink()

    # -- actions -------------------------------------------------------------
    def action_activate(self):
        for plan in self:
            if not plan.template_ids:
                raise UserError(_("Plan '%s' has no gate templates.") % plan.display_name)
            siblings = self.search(
                [
                    ("code", "=", plan.code),
                    ("company_id", "=", plan.company_id.id),
                    ("state", "=", "active"),
                    ("id", "!=", plan.id),
                ]
            )
            siblings.write({"state": "superseded"})
            plan.state = "active"
        return True

    def action_archive_plan(self):
        self.write({"state": "archived", "active": False})
        return True

    def action_new_version(self):
        """Copy the whole configuration tree into a fresh draft version."""
        self.ensure_one()
        next_version = (
            max(
                self.search([("code", "=", self.code), ("company_id", "=", self.company_id.id)])
                .mapped("version")
                or [self.version]
            )
            + 1
        )
        new_plan = self.copy(
            {
                "version": next_version,
                "state": "draft",
                "predecessor_id": self.id,
                "name": self.name,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "sgc.ces.gate.plan",
            "res_id": new_plan.id,
            "view_mode": "form",
            "target": "current",
        }

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault("state", "draft")
        default.setdefault("assignment_ids", [])
        if "version" not in default:
            default["version"] = self.version + 1
        return super().copy(default)

    # -- resolution ----------------------------------------------------------
    @api.model
    def _resolve_plan_for_employee(self, employee):
        """No routing: the one active default plan for the employee's company."""
        employee = employee.sudo()
        if not employee:
            return self.browse()
        company = employee.company_id or self.env.company
        return self.sudo().search(
            [("state", "=", "active"), ("company_id", "=", company.id), ("is_default", "=", True)],
            order="version desc",
            limit=1,
        )
