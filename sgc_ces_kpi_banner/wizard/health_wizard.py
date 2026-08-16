# -*- coding: utf-8 -*-
"""Configuration-health wizard: makes the known data blockers visible."""
from odoo import api, fields, models


class SgcCesHealthWizard(models.TransientModel):
    _name = "sgc.ces.health.wizard"
    _description = "SGC CES Configuration Health Check"

    report = fields.Text(readonly=True)
    has_errors = fields.Boolean(readonly=True)

    def action_refresh(self):
        for wizard in self:
            issues = self.env["sgc.ces.kpi.service"].configuration_health()
            wizard.has_errors = any(i["level"] == "error" for i in issues)
            if not issues:
                wizard.report = "OK - no configuration issues detected."
            else:
                wizard.report = "\n".join(
                    "[%s] %s: %s" % (i["level"].upper(), i["code"], i["message"]) for i in issues
                )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def action_open(self):
        wizard = self.create({})
        return wizard.action_refresh()
