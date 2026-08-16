# -*- coding: utf-8 -*-
"""Activity metric provider - daily/monthly effort KPIs.

Counts are derived from native Odoo records only:

* ``activity_logged_count``        - ``mail.message`` of subtype
  ``mail.mt_note`` / activity-done messages authored by the user on
  ``crm.lead`` records.
* ``activity_lead_touch_count``    - distinct opportunities owned by the user
  whose ``write_date`` falls inside the window.
* ``activity_stage_advance_count`` - opportunities whose
  ``date_last_stage_update`` falls inside the window.

No target values are invented here; targets come from ``sgc.ces.kpi.target``
configuration records created by an administrator.
"""
from odoo import api, models


class SgcCesMetricActivity(models.AbstractModel):
    _name = "sgc.ces.metric.activity"
    _description = "SGC CES Activity Metric Provider"

    @api.model
    def _lead_domain(self, ctx, date_field):
        domain = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("user_id", "=", ctx["user_id"]),
        ]
        if ctx.get("date_from"):
            domain.append((date_field, ">=", "%s 00:00:00" % ctx["date_from"]))
        if ctx.get("date_to"):
            domain.append((date_field, "<=", "%s 23:59:59" % ctx["date_to"]))
        if ctx.get("company_ids"):
            domain.append(("company_id", "in", list(ctx["company_ids"]) + [False]))
        return domain

    @api.model
    def _metric_activity_lead_touch_count(self, ctx):
        domain = self._lead_domain(ctx, "write_date")
        count = self.env["crm.lead"].sudo().search_count(domain)
        return {"value": float(count), "domain": domain, "res_model": "crm.lead"}

    @api.model
    def _metric_activity_stage_advance_count(self, ctx):
        domain = self._lead_domain(ctx, "date_last_stage_update")
        count = self.env["crm.lead"].sudo().search_count(domain)
        return {"value": float(count), "domain": domain, "res_model": "crm.lead"}

    @api.model
    def _metric_activity_logged_count(self, ctx):
        user = self.env["res.users"].sudo().browse(ctx["user_id"])
        partner = user.partner_id
        domain = [
            ("model", "=", "crm.lead"),
            ("author_id", "=", partner.id if partner else 0),
            ("message_type", "in", ("comment", "notification")),
        ]
        if ctx.get("date_from"):
            domain.append(("date", ">=", "%s 00:00:00" % ctx["date_from"]))
        if ctx.get("date_to"):
            domain.append(("date", "<=", "%s 23:59:59" % ctx["date_to"]))
        count = self.env["mail.message"].sudo().search_count(domain)
        # mail.message is not a safe drill-down target for a CES user.
        return {"value": float(count), "domain": None, "res_model": None}
