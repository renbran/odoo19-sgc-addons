# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SgcGateOverrideWizard(models.TransientModel):
    _name = "sgc.gate.override.wizard"
    _description = "Override the Proposal-stage qualification gate"

    lead_id = fields.Many2one("crm.lead", string="Opportunity", required=True)
    gate_status = fields.Selection(related="lead_id.x_gate_status", readonly=True)
    gate_answered_count = fields.Integer(related="lead_id.x_gate_answered_count", readonly=True)
    reason = fields.Text(string="Override Reason", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("sales_team.group_sale_manager"):
            raise UserError(_("Only a Sales Manager can override the qualification gate."))
        if not (self.reason or "").strip():
            raise UserError(_("An override reason is required."))

        gate_stage_id = self.lead_id._get_gate_stage_id()
        self.lead_id.write(
            {
                "stage_id": gate_stage_id,
                "x_gate_override_reason": self.reason,
            }
        )
        return {"type": "ir.actions.act_window_close"}
