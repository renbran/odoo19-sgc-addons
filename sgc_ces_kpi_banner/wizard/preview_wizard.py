# -*- coding: utf-8 -*-
"""Preview a plan's schedule for an employee without creating anything."""
from odoo import _, api, fields, models


class SgcCesPreviewWizard(models.TransientModel):
    _name = "sgc.ces.preview.wizard"
    _description = "SGC CES Gate Schedule Preview"

    plan_id = fields.Many2one("sgc.ces.gate.plan", required=True)
    employee_id = fields.Many2one("hr.employee", required=True)
    anchor_date = fields.Date(readonly=True)
    preview = fields.Text(readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if self.env.context.get("active_model") == "sgc.ces.gate.plan":
            values["plan_id"] = self.env.context.get("active_id")
        return values

    @api.onchange("plan_id", "employee_id")
    def _onchange_preview(self):
        for wizard in self:
            wizard.preview = wizard._build_preview()

    def _build_preview(self):
        self.ensure_one()
        if not (self.plan_id and self.employee_id):
            return ""
        identity = self.env["sgc.ces.identity"]
        anchor = identity.ces_start_date(self.employee_id, self.plan_id.start_date_strategy)
        self.anchor_date = anchor
        if not anchor:
            return _("No CES start date could be resolved for this employee.")
        lines = [_("Anchor date: %s") % fields.Date.to_string(anchor), ""]
        previous_due = None
        for template in self.plan_id.template_ids.sorted(
            key=lambda t: (t.sequence, t.offset_months, t.id)
        ):
            base = previous_due if template.anchor == "previous_gate_due" and previous_due else anchor
            start, end, due, review = template.compute_schedule(base)
            previous_due = due
            lines.append(
                "%s: %s -> %s | due %s | review alert %s"
                % (
                    template.name,
                    fields.Date.to_string(start),
                    fields.Date.to_string(end),
                    fields.Date.to_string(due),
                    fields.Date.to_string(review),
                )
            )
        return "\n".join(lines)

    def action_refresh(self):
        self.ensure_one()
        self.preview = self._build_preview()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
