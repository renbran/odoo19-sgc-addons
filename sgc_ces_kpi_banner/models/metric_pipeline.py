# -*- coding: utf-8 -*-
"""Pipeline metric provider.

"Qualifying pipeline" is configurable through requirement parameters:

* ``min_expected_revenue``  - ignore opportunities below this amount
* ``proposal_only``         - restrict to the configured Proposal stage
* ``include_won``           - count the Won stage as pipeline (off by default)
* ``probability_min``       - minimum win probability (0-100)

Stage identifiers are resolved via ``sgc.ces.identity`` (config parameter,
then name lookup); no stage id is hard coded.
"""
from odoo import api, models


class SgcCesMetricPipeline(models.AbstractModel):
    _name = "sgc.ces.metric.pipeline"
    _description = "SGC CES Pipeline Metric Provider"

    @api.model
    def _pipeline_domain(self, ctx):
        params = ctx.get("params") or {}
        identity = self.env["sgc.ces.identity"]
        domain = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("user_id", "=", ctx["user_id"]),
        ]
        if params.get("proposal_only"):
            stage = identity.proposal_stage()
            if stage:
                domain.append(("stage_id", "=", stage.id))
        else:
            excluded = identity.excluded_stage_ids()
            if params.get("include_won"):
                won = identity.won_stage()
                if won and won.id in excluded:
                    excluded = [sid for sid in excluded if sid != won.id]
            if excluded:
                domain.append(("stage_id", "not in", excluded))
        minimum = params.get("min_expected_revenue")
        if minimum:
            domain.append(("expected_revenue", ">=", float(minimum)))
        probability_min = params.get("probability_min")
        if probability_min:
            domain.append(("probability", ">=", float(probability_min)))
        date_from = ctx.get("date_from")
        date_to = ctx.get("date_to")
        date_field = params.get("date_field") or "create_date"
        if date_field not in ("create_date", "date_open", "date_last_stage_update"):
            date_field = "create_date"
        if date_from:
            domain.append((date_field, ">=", "%s 00:00:00" % date_from))
        if date_to:
            domain.append((date_field, "<=", "%s 23:59:59" % date_to))
        company_ids = ctx.get("company_ids")
        if company_ids:
            domain.append(("company_id", "in", list(company_ids) + [False]))
        return domain

    @api.model
    def _metric_pipeline_qualified_value(self, ctx):
        domain = self._pipeline_domain(ctx)
        groups = self.env["crm.lead"].sudo()._read_group(domain, [], ["expected_revenue:sum"])
        value = (groups[0][0] or 0.0) if groups else 0.0
        return {"value": float(value), "domain": domain, "res_model": "crm.lead"}

    @api.model
    def _metric_pipeline_qualified_count(self, ctx):
        domain = self._pipeline_domain(ctx)
        count = self.env["crm.lead"].sudo().search_count(domain)
        return {"value": float(count), "domain": domain, "res_model": "crm.lead"}

    @api.model
    def _metric_pipeline_proposal_value(self, ctx):
        ctx = dict(ctx)
        params = dict(ctx.get("params") or {})
        params["proposal_only"] = True
        ctx["params"] = params
        return self._metric_pipeline_qualified_value(ctx)
