# -*- coding: utf-8 -*-
"""Staleness metric provider.

Source field selection (verified against the live database, see
``odoo-ces-kpi-verification-addendum.md`` section 8):

* ``date_last_stage_update`` - DEFAULT.  Native, written on every stage
  change, 100% populated.
* ``x_last_activity_date``   - optional alternate.  Only written by the
  Apollo/Hunter/LLM enrichment crons, so it means "last enrichment run",
  not "last customer touch".  Selecting it is allowed but carries an
  explicit caveat in the UI help text.
* ``x_days_since_activity``  - deliberately NOT offered.  Declared by
  ``sgc_lead_scoring`` but never written by any code path; it is a dead
  field and would silently produce wrong answers.

Health bands: ``healthy`` < warn_days <= ``at_risk`` < stale_days <=
``stale``; an opportunity whose source field is empty is ``unknown`` and is
never counted as stale.
"""
from datetime import timedelta

from odoo import api, fields, models

ALLOWED_SOURCE_FIELDS = ("date_last_stage_update", "x_last_activity_date")
DEFAULT_SOURCE_FIELD = "date_last_stage_update"
DEFAULT_STALE_DAYS = 45
DEFAULT_WARN_DAYS = 30


class SgcCesMetricStaleness(models.AbstractModel):
    _name = "sgc.ces.metric.staleness"
    _description = "SGC CES Staleness Metric Provider"

    @api.model
    def _source_field(self, params):
        field_name = (params or {}).get("staleness_field") or DEFAULT_SOURCE_FIELD
        if field_name not in ALLOWED_SOURCE_FIELDS:
            field_name = DEFAULT_SOURCE_FIELD
        if field_name not in self.env["crm.lead"]._fields:
            field_name = DEFAULT_SOURCE_FIELD
        return field_name

    @api.model
    def _base_domain(self, ctx):
        identity = self.env["sgc.ces.identity"]
        domain = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("user_id", "=", ctx["user_id"]),
        ]
        params = ctx.get("params") or {}
        if params.get("proposal_only"):
            stage = identity.proposal_stage()
            if stage:
                domain.append(("stage_id", "=", stage.id))
        else:
            excluded = identity.excluded_stage_ids()
            if excluded:
                domain.append(("stage_id", "not in", excluded))
        company_ids = ctx.get("company_ids")
        if company_ids:
            domain.append(("company_id", "in", list(company_ids) + [False]))
        return domain

    @api.model
    def _stale_cutoff(self, ctx, days):
        reference = ctx.get("date_to") or fields.Date.context_today(self)
        reference = fields.Date.to_date(reference)
        return reference - timedelta(days=int(days))

    @api.model
    def _metric_staleness_stale_count(self, ctx):
        params = ctx.get("params") or {}
        field_name = self._source_field(params)
        stale_days = int(params.get("stale_days") or DEFAULT_STALE_DAYS)
        cutoff = self._stale_cutoff(ctx, stale_days)
        domain = self._base_domain(ctx)
        # Strictly older than the cutoff day: an opportunity touched exactly
        # ``stale_days`` ago is NOT yet stale (day-boundary rule, tested).
        domain.append((field_name, "<", "%s 00:00:00" % cutoff))
        count = self.env["crm.lead"].sudo().search_count(domain)
        return {
            "value": float(count),
            "domain": domain,
            "res_model": "crm.lead",
            "detail": {"source_field": field_name, "stale_days": stale_days,
                       "cutoff": fields.Date.to_string(cutoff)},
        }

    @api.model
    def _band_counts(self, ctx):
        params = ctx.get("params") or {}
        field_name = self._source_field(params)
        stale_days = int(params.get("stale_days") or DEFAULT_STALE_DAYS)
        warn_days = int(params.get("warn_days") or DEFAULT_WARN_DAYS)
        if warn_days > stale_days:
            warn_days = stale_days
        base = self._base_domain(ctx)
        Lead = self.env["crm.lead"].sudo()
        total = Lead.search_count(base)
        unknown = Lead.search_count(base + [(field_name, "=", False)])
        stale_cutoff = self._stale_cutoff(ctx, stale_days)
        warn_cutoff = self._stale_cutoff(ctx, warn_days)
        stale = Lead.search_count(base + [(field_name, "<", "%s 00:00:00" % stale_cutoff)])
        at_risk = Lead.search_count(
            base
            + [
                (field_name, "<", "%s 00:00:00" % warn_cutoff),
                (field_name, ">=", "%s 00:00:00" % stale_cutoff),
            ]
        )
        healthy = max(total - unknown - stale - at_risk, 0)
        return {
            "total": total,
            "unknown": unknown,
            "stale": stale,
            "at_risk": at_risk,
            "healthy": healthy,
            "source_field": field_name,
            "stale_days": stale_days,
            "warn_days": warn_days,
            "base_domain": base,
        }

    @api.model
    def _metric_staleness_stale_ratio(self, ctx):
        bands = self._band_counts(ctx)
        known = bands["total"] - bands["unknown"]
        ratio = (bands["stale"] / known * 100.0) if known else 0.0
        domain = bands.pop("base_domain")
        return {"value": ratio, "domain": domain, "res_model": "crm.lead", "detail": bands}

    @api.model
    def _metric_staleness_healthy_ratio(self, ctx):
        bands = self._band_counts(ctx)
        known = bands["total"] - bands["unknown"]
        ratio = (bands["healthy"] / known * 100.0) if known else 0.0
        domain = bands.pop("base_domain")
        return {"value": ratio, "domain": domain, "res_model": "crm.lead", "detail": bands}
