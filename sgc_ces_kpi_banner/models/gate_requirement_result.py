# -*- coding: utf-8 -*-
"""One measured requirement inside a gate instance.

The definition (metric code, comparator, target, window, parameters) is
snapshotted from the requirement at instance creation time; the *measurement*
is live and refreshed on demand.  ``params_json`` is stored and read with
``json.loads`` - structured data, never code.
"""
import json
import logging

from odoo import _, api, fields, models

from .metric_registry import (
    COMPARATOR_SELECTION,
    METRIC_SELECTION,
    WINDOW_SELECTION,
    compare,
    progress_ratio,
)

_logger = logging.getLogger(__name__)


class SgcCesGateRequirementResult(models.Model):
    _name = "sgc.ces.gate.requirement.result"
    _description = "SGC CES Gate Requirement Result"
    _order = "instance_id, sequence, id"

    name = fields.Char(required=True, readonly=True)
    instance_id = fields.Many2one(
        "sgc.ces.gate.instance", required=True, ondelete="cascade", index=True, readonly=True
    )
    requirement_id = fields.Many2one("sgc.ces.gate.requirement", readonly=True, ondelete="set null")
    company_id = fields.Many2one(
        "res.company", related="instance_id.company_id", store=True, index=True
    )
    user_id = fields.Many2one("res.users", related="instance_id.user_id", store=True, index=True)
    sequence = fields.Integer(default=10, readonly=True)

    metric_code = fields.Selection(METRIC_SELECTION, required=True, readonly=True)
    comparator = fields.Selection(COMPARATOR_SELECTION, required=True, readonly=True)
    original_target = fields.Float(required=True, readonly=True, digits=(16, 2))
    measurement_window = fields.Selection(WINDOW_SELECTION, required=True, readonly=True)
    level = fields.Selection(
        [("mandatory", "Mandatory"), ("weighted", "Weighted"), ("informational", "Informational")],
        required=True,
        readonly=True,
    )
    weight = fields.Float(default=1.0, readonly=True)
    params_json = fields.Text(readonly=True, default="{}")
    help_text = fields.Text(readonly=True)

    measured_value = fields.Float(readonly=True, digits=(16, 2))
    measured_on = fields.Datetime(readonly=True)
    measurement_error = fields.Char(readonly=True)
    drilldown_json = fields.Text(readonly=True)

    effective_target = fields.Float(compute="_compute_effective_target", store=True, digits=(16, 2))
    achieved = fields.Boolean(compute="_compute_achieved", store=True)
    progress = fields.Float(compute="_compute_achieved", store=True)

    # ------------------------------------------------------------------ util
    def params(self):
        self.ensure_one()
        try:
            data = json.loads(self.params_json or "{}")
        except (TypeError, ValueError):
            _logger.warning("sgc_ces_kpi_banner: unreadable params on result %s", self.id)
            return {}
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------- computed
    @api.depends(
        "original_target",
        "instance_id.consideration_ids.state",
        "instance_id.consideration_ids.consideration_type",
        "instance_id.consideration_ids.requirement_result_id",
        "instance_id.consideration_ids.adjusted_target",
    )
    def _compute_effective_target(self):
        """Additive only: the original target is never mutated."""
        for result in self:
            target = result.original_target
            considerations = result.instance_id.consideration_ids.filtered(
                lambda c: c.state == "approved"
                and c.consideration_type == "target_adjustment"
                and (not c.requirement_result_id or c.requirement_result_id.id == result.id)
            )
            for consideration in considerations.sorted(key=lambda c: c.id):
                target = consideration.adjusted_target
            result.effective_target = target

    @api.depends("measured_value", "effective_target", "comparator")
    def _compute_achieved(self):
        for result in self:
            try:
                result.achieved = compare(
                    result.measured_value, result.comparator, result.effective_target
                )
                result.progress = progress_ratio(
                    result.measured_value, result.comparator, result.effective_target
                )
            except Exception:  # noqa: BLE001
                result.achieved = False
                result.progress = 0.0

    # ---------------------------------------------------------- measurement
    def _context_for_metric(self):
        self.ensure_one()
        instance = self.instance_id
        registry = self.env["sgc.ces.metric.registry"]
        params = self.params()
        date_from, date_to = registry.resolve_window(
            self.measurement_window,
            params=params,
            gate_start=instance.period_start,
            ces_start=instance.assignment_id.ces_start_date,
        )
        return {
            "user_id": instance.user_id.id,
            "date_from": date_from,
            "date_to": date_to,
            "params": params,
            "company_ids": instance.company_id.ids,
        }

    def evaluate(self):
        registry = self.env["sgc.ces.metric.registry"]
        for result in self:
            if not result.instance_id.user_id:
                result.write({"measurement_error": _("Employee has no linked user."),
                              "measured_value": 0.0,
                              "measured_on": fields.Datetime.now()})
                continue
            outcome = registry.safe_evaluate(result.metric_code, result._context_for_metric())
            result.write(
                {
                    "measured_value": outcome.get("value") or 0.0,
                    "measured_on": fields.Datetime.now(),
                    "measurement_error": outcome.get("error") or False,
                    "drilldown_json": json.dumps(
                        {
                            "res_model": outcome.get("res_model"),
                            "domain": outcome.get("domain"),
                        }
                    ),
                }
            )
        return True

    # -------------------------------------------------------------- actions
    def action_open_drilldown(self):
        """Open the server-generated drill-down. The domain is never client supplied."""
        self.ensure_one()
        self.evaluate()
        try:
            payload = json.loads(self.drilldown_json or "{}")
        except (TypeError, ValueError):
            payload = {}
        res_model = payload.get("res_model")
        domain = payload.get("domain")
        if not res_model or domain is None:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "message": _("This measurement has no safe drill-down view."),
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": res_model,
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "domain": domain,
            "target": "current",
        }

    def summary_dict(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "metric_code": self.metric_code,
            "unit": self.env["sgc.ces.metric.registry"].metric_unit(self.metric_code),
            "comparator": self.comparator,
            "target": self.effective_target,
            "original_target": self.original_target,
            "value": self.measured_value,
            "progress": round(self.progress * 100.0, 1),
            "achieved": self.achieved,
            "level": self.level,
            "help_text": self.help_text or "",
            "error": self.measurement_error or "",
            "has_drilldown": bool(self.drilldown_json and self.drilldown_json != "{}"),
        }
