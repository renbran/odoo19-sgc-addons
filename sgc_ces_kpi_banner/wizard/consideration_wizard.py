# -*- coding: utf-8 -*-
"""Raise a target adjustment against a gate requirement.

Extension has its own dedicated wizard (extension_wizard.py) since it needs
a due-date picker; this one is target-adjustment only."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SgcCesConsiderationWizard(models.TransientModel):
    _name = "sgc.ces.consideration.wizard"
    _description = "SGC CES Target Adjustment Wizard"

    instance_id = fields.Many2one("sgc.ces.gate.instance", required=True)
    requirement_result_id = fields.Many2one(
        "sgc.ces.gate.requirement.result",
        domain="[('instance_id', '=', instance_id)]",
        string="Applies to requirement",
        required=True,
    )
    adjusted_target = fields.Float(digits=(16, 2))
    reason = fields.Text(required=True)
    approve_now = fields.Boolean(
        string="Approve immediately",
        help="Only available to the resolved reviewer or a CES KPI administrator.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get("active_model") == "sgc.ces.gate.instance":
            values["instance_id"] = self.env.context.get("active_id")
        return values

    def action_confirm(self):
        self.ensure_one()
        consideration = self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": self.instance_id.id,
                "requirement_result_id": self.requirement_result_id.id,
                "consideration_type": "target_adjustment",
                "adjusted_target": self.adjusted_target,
                "reason": self.reason,
            }
        )
        if self.approve_now:
            consideration.action_approve()
        return {"type": "ir.actions.act_window_close"}
