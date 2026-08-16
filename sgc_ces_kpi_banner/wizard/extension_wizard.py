# -*- coding: utf-8 -*-
"""Grant a gate extension. Additive - the original due date is preserved."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SgcCesExtensionWizard(models.TransientModel):
    _name = "sgc.ces.extension.wizard"
    _description = "SGC CES Gate Extension Wizard"

    instance_id = fields.Many2one("sgc.ces.gate.instance", required=True)
    original_due_date = fields.Date(related="instance_id.due_date", readonly=True)
    new_due_date = fields.Date(required=True)
    reason = fields.Text(required=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get("active_model") == "sgc.ces.gate.instance":
            values["instance_id"] = self.env.context.get("active_id")
        return values

    def action_confirm(self):
        self.ensure_one()
        if self.instance_id.due_date and self.new_due_date <= self.instance_id.due_date:
            raise UserError(_("The new due date must be later than the original due date."))
        consideration = self.env["sgc.ces.gate.consideration"].create(
            {
                "instance_id": self.instance_id.id,
                "consideration_type": "extension",
                "new_due_date": self.new_due_date,
                "reason": self.reason,
            }
        )
        consideration.action_approve()
        return {"type": "ir.actions.act_window_close"}
