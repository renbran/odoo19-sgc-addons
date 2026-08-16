# -*- coding: utf-8 -*-
"""Explicit metric dispatch table.

SECURITY CONTRACT
-----------------
A gate requirement stores a *metric code* (a plain string chosen from a
closed selection) and a handful of typed scalar parameters.  It never stores
a domain, a Python expression or SQL.  Evaluation goes through
``METRIC_DISPATCH`` below, which maps a code to ``(model name, method name)``
pairs that exist in this addon's source.  An unknown code raises instead of
falling through to anything dynamic.  No dynamic-evaluation helper of any kind
and no string-built SQL exists anywhere in the metric layer; the test suite
enforces this with a static source scan (see ``tests/test_d_requirements.py``).
"""
import logging
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# code -> (model, method)
METRIC_DISPATCH = {
    "pipeline_qualified_value": ("sgc.ces.metric.pipeline", "_metric_pipeline_qualified_value"),
    "pipeline_qualified_count": ("sgc.ces.metric.pipeline", "_metric_pipeline_qualified_count"),
    "pipeline_proposal_value": ("sgc.ces.metric.pipeline", "_metric_pipeline_proposal_value"),
    "staleness_stale_count": ("sgc.ces.metric.staleness", "_metric_staleness_stale_count"),
    "staleness_stale_ratio": ("sgc.ces.metric.staleness", "_metric_staleness_stale_ratio"),
    "staleness_healthy_ratio": ("sgc.ces.metric.staleness", "_metric_staleness_healthy_ratio"),
    "signed_proposal_count": ("sgc.ces.metric.signature", "_metric_signed_proposal_count"),
    "signed_proposal_value": ("sgc.ces.metric.signature", "_metric_signed_proposal_value"),
    "paid_deal_count": ("sgc.ces.metric.payment", "_metric_paid_deal_count"),
    "paid_deal_value": ("sgc.ces.metric.payment", "_metric_paid_deal_value"),
    "activity_logged_count": ("sgc.ces.metric.activity", "_metric_activity_logged_count"),
    "activity_lead_touch_count": ("sgc.ces.metric.activity", "_metric_activity_lead_touch_count"),
    "activity_stage_advance_count": ("sgc.ces.metric.activity", "_metric_activity_stage_advance_count"),
}

METRIC_SELECTION = [
    ("pipeline_qualified_value", "Pipeline - qualified value"),
    ("pipeline_qualified_count", "Pipeline - qualified opportunity count"),
    ("pipeline_proposal_value", "Pipeline - value in Proposal stage"),
    ("staleness_stale_count", "Staleness - stale opportunity count"),
    ("staleness_stale_ratio", "Staleness - stale ratio (%)"),
    ("staleness_healthy_ratio", "Staleness - healthy ratio (%)"),
    ("signed_proposal_count", "Signed proposal - count"),
    ("signed_proposal_value", "Signed proposal - value"),
    ("paid_deal_count", "Paid deal - count"),
    ("paid_deal_value", "Paid deal - value"),
    ("activity_logged_count", "Activity - logged activities"),
    ("activity_lead_touch_count", "Activity - opportunities touched"),
    ("activity_stage_advance_count", "Activity - stage advances"),
]

METRIC_UNITS = {
    "pipeline_qualified_value": "currency",
    "pipeline_proposal_value": "currency",
    "signed_proposal_value": "currency",
    "paid_deal_value": "currency",
    "staleness_stale_ratio": "percent",
    "staleness_healthy_ratio": "percent",
}

COMPARATOR_SELECTION = [
    (">=", "at least (>=)"),
    (">", "more than (>)"),
    ("<=", "at most (<=)"),
    ("<", "less than (<)"),
    ("==", "exactly (=)"),
    ("!=", "different from (!=)"),
]

WINDOW_SELECTION = [
    ("since_gate_start", "Since gate period start"),
    ("since_ces_start", "Since CES start date"),
    ("rolling_days", "Rolling window (days)"),
    ("current_day", "Today"),
    ("current_month", "Current calendar month"),
    ("all_time", "All time"),
]

# Direction in which "better" moves. Used for progress bars and status maths.
LOWER_IS_BETTER = {"<", "<="}


def compare(value, comparator, target):
    """Pure comparison helper - no dynamic evaluation."""
    if comparator == ">=":
        return value >= target
    if comparator == ">":
        return value > target
    if comparator == "<=":
        return value <= target
    if comparator == "<":
        return value < target
    if comparator == "==":
        return abs(value - target) < 1e-9
    if comparator == "!=":
        return abs(value - target) >= 1e-9
    raise UserError(_("Unsupported comparison operator %s") % comparator)


def progress_ratio(value, comparator, target):
    """Return a 0..1 completion ratio, direction aware."""
    if comparator in LOWER_IS_BETTER:
        if value <= target:
            return 1.0
        if value <= 0:
            return 1.0
        # How far above the ceiling are we? 2x the ceiling means 0%.
        if target <= 0:
            return 0.0
        overshoot = (value - target) / max(target, 1e-9)
        return max(0.0, 1.0 - min(overshoot, 1.0))
    if target <= 0:
        return 1.0 if compare(value, comparator, target) else 0.0
    return max(0.0, min(value / target, 1.0))


class SgcCesMetricRegistry(models.AbstractModel):
    _name = "sgc.ces.metric.registry"
    _description = "SGC CES Metric Registry (explicit dispatch, no eval)"

    @api.model
    def metric_selection(self):
        return list(METRIC_SELECTION)

    @api.model
    def metric_unit(self, code):
        return METRIC_UNITS.get(code, "unit")

    # -- window resolution ---------------------------------------------------
    @api.model
    def resolve_window(self, window, params=None, gate_start=None, ces_start=None, reference=None):
        """Return an inclusive ``(date_from, date_to)`` tuple of ``date`` objects.

        ``date_from`` may be ``None`` meaning "no lower bound".
        """
        params = params or {}
        today = fields.Date.to_date(reference) if reference else fields.Date.context_today(self)
        if window == "current_day":
            return today, today
        if window == "current_month":
            return today.replace(day=1), today
        if window == "rolling_days":
            days = int(params.get("window_days") or 30)
            return today - timedelta(days=max(days, 0)), today
        if window == "since_gate_start":
            return fields.Date.to_date(gate_start) if gate_start else None, today
        if window == "since_ces_start":
            return fields.Date.to_date(ces_start) if ces_start else None, today
        # all_time
        return None, today

    # -- dispatch ------------------------------------------------------------
    @api.model
    def evaluate(self, metric_code, ctx):
        """Evaluate one metric.

        ``ctx`` keys: ``user_id`` (int, required), ``date_from``/``date_to``
        (``date`` or ``None``), ``params`` (dict of scalars).

        Returns ``{'value', 'unit', 'code', 'domain', 'res_model', 'detail'}``.
        ``domain`` is always *built server side* from the resolved records so a
        drill-down never trusts a client supplied filter.
        """
        target = METRIC_DISPATCH.get(metric_code)
        if not target:
            raise UserError(_("Unknown metric code '%s'.") % metric_code)
        model_name, method_name = target
        provider = self.env[model_name]
        method = getattr(provider, method_name, None)
        if method is None:
            raise UserError(_("Metric provider %s is missing method %s.") % (model_name, method_name))
        ctx = dict(ctx or {})
        ctx.setdefault("params", {})
        result = method(ctx)
        result.setdefault("code", metric_code)
        result.setdefault("unit", self.metric_unit(metric_code))
        result.setdefault("domain", None)
        result.setdefault("res_model", None)
        result.setdefault("detail", {})
        return result

    @api.model
    def safe_evaluate(self, metric_code, ctx):
        """``evaluate`` wrapped so one broken metric cannot break the banner."""
        try:
            return self.evaluate(metric_code, ctx)
        except Exception as exc:  # noqa: BLE001 - deliberate isolation boundary
            _logger.exception("sgc_ces_kpi_banner: metric %s failed", metric_code)
            return {
                "code": metric_code,
                "value": 0.0,
                "unit": self.metric_unit(metric_code),
                "domain": None,
                "res_model": None,
                "error": str(exc),
                "detail": {},
            }
