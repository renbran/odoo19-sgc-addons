# -*- coding: utf-8 -*-
"""Compact manager review wizard - decide without leaving the list view."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SgcCesReviewWizard(models.TransientModel):
    _name = "sgc.ces.review.wizard"
    _description = "SGC CES Gate Review Wizard"

    review_id = fields.Many2one("sgc.ces.gate.review", required=True, readonly=True)
    instance_id = fields.Many2one(
        "sgc.ces.gate.instance", related="review_id.instance_id", readonly=True
    )
    summary = fields.Text(readonly=True)
    decision = fields.Selection(
        [
            ("pass", "Met - pass the gate"),
            ("fail", "Not met - fail the gate"),
            ("extend", "Grant an extension"),
            ("defer", "Defer the decision"),
        ],
        required=True,
    )
    decision_notes = fields.Text()
    new_due_date = fields.Date(help="Required when granting an extension.")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        review_id = self.env.context.get("active_id")
        if self.env.context.get("active_model") == "sgc.ces.gate.review" and review_id:
            review = self.env["sgc.ces.gate.review"].browse(review_id)
            values["review_id"] = review.id
            review.instance_id.evaluate()
            values["summary"] = review.instance_id._review_body_text().replace("<br/>", "\n")
        return values

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "extend" and not self.new_due_date:
            raise UserError(_("Choose the new due date for the extension."))
        self.review_id.write(
            {"decision": self.decision, "decision_notes": self.decision_notes}
        )
        if self.decision == "extend":
            self.env["sgc.ces.gate.consideration"].create(
                {
                    "instance_id": self.instance_id.id,
                    "consideration_type": "extension",
                    "new_due_date": self.new_due_date,
                    "reason": self.decision_notes or _("Extension granted during review."),
                    "state": "approved",
                    "review_id": self.review_id.id,
                    "approved_by_id": self.env.uid,
                    "approved_on": fields.Datetime.now(),
                }
            )
        self.review_id.action_submit()
        self.review_id.action_apply()
        return {"type": "ir.actions.act_window_close"}
