# -*- coding: utf-8 -*-
"""Considerations: extensions and target adjustments.

Considerations are strictly ADDITIVE.  They never write back onto the gate
instance's ``due_date`` or onto a requirement result's ``original_target``.
The effective due date and effective target are computed by layering approved
considerations on top of the untouched originals, so the original commitment
stays auditable forever.
"""
from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SgcCesGateConsideration(models.Model):
    _name = "sgc.ces.gate.consideration"
    _description = "SGC CES Gate Consideration"
    _inherit = ["mail.thread"]
    _order = "instance_id, id"

    name = fields.Char(compute="_compute_name", store=True)
    instance_id = fields.Many2one(
        "sgc.ces.gate.instance", required=True, ondelete="cascade", index=True
    )
    requirement_result_id = fields.Many2one(
        "sgc.ces.gate.requirement.result",
        string="Applies to requirement",
        help="Leave empty to apply the adjustment to every requirement of the gate.",
        ondelete="cascade",
    )
    review_id = fields.Many2one("sgc.ces.gate.review", readonly=True, ondelete="set null")
    employee_id = fields.Many2one(
        "hr.employee", related="instance_id.employee_id", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company", related="instance_id.company_id", store=True, index=True
    )

    consideration_type = fields.Selection(
        [
            ("extension", "Extension"),
            ("target_adjustment", "Target adjustment"),
        ],
        required=True,
        default="extension",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("revoked", "Revoked"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )
    reason = fields.Text(required=True)
    new_due_date = fields.Date(help="Extension only. Must be later than the original due date.")
    adjusted_target = fields.Float(
        digits=(16, 2), help="Target adjustment only. The original target is preserved."
    )
    requested_by_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, readonly=True
    )
    approved_by_id = fields.Many2one("res.users", readonly=True)
    approved_on = fields.Datetime(readonly=True)

    original_due_date = fields.Date(related="instance_id.due_date", store=True, readonly=True)

    @api.depends("consideration_type", "instance_id.name")
    def _compute_name(self):
        labels = dict(self._fields["consideration_type"].selection)
        for record in self:
            record.name = "%s - %s" % (
                labels.get(record.consideration_type, ""),
                record.instance_id.name or "",
            )

    @api.constrains("consideration_type", "new_due_date", "adjusted_target", "instance_id")
    def _check_payload(self):
        for record in self:
            if record.consideration_type == "extension":
                if not record.new_due_date:
                    raise ValidationError(_("An extension requires a new due date."))
                if record.instance_id.due_date and record.new_due_date <= record.instance_id.due_date:
                    raise ValidationError(
                        _("The extended due date must be later than the original due date (%s).")
                        % fields.Date.to_string(record.instance_id.due_date)
                    )
            if record.consideration_type == "target_adjustment" and record.adjusted_target < 0:
                raise ValidationError(_("An adjusted target cannot be negative."))

    def _check_approver(self):
        if self.env.su or self.env.uid == SUPERUSER_ID:
            return
        if self.env.user.has_group("sgc_ces_kpi_banner.group_ces_kpi_admin"):
            return
        for record in self:
            manager = record.instance_id.manager_user_id
            if manager and manager.id == self.env.uid:
                continue
            raise UserError(
                _("Only the resolved reviewer or a CES KPI administrator can approve a "
                  "consideration.")
            )

    def action_approve(self):
        self._check_approver()
        self.write(
            {
                "state": "approved",
                "approved_by_id": self.env.uid,
                "approved_on": fields.Datetime.now(),
            }
        )
        for record in self:
            record.instance_id.message_post(
                body=_("Consideration approved: %s - %s") % (record.name, record.reason),
                subtype_xmlid="mail.mt_note",
            )
            if record.consideration_type == "extension":
                record.instance_id.state = "extended"
        return True

    def action_reject(self):
        self._check_approver()
        self.write({"state": "rejected"})
        return True

    def action_revoke(self):
        self._check_approver()
        self.write({"state": "revoked"})
        return True

    def write(self, vals):
        frozen = {"consideration_type", "new_due_date", "adjusted_target", "instance_id"}
        if frozen & set(vals):
            for record in self:
                if record.state == "approved":
                    raise UserError(
                        _("An approved consideration is immutable; revoke it and create a "
                          "new one instead.")
                    )
        return super().write(vals)
