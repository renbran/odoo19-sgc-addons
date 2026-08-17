# -*- coding: utf-8 -*-
"""Central server-side KPI service.

Every number the banner displays is computed here.  The JavaScript layer
never re-implements a formula, never builds a domain and never reads an
accounting model.  Drill-down actions are produced server side and validated
against a whitelist of models the caller is allowed to reach.
"""
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import config

from .metric_registry import compare, progress_ratio

_logger = logging.getLogger(__name__)

# Models a drill-down is ever allowed to open.
DRILLDOWN_WHITELIST = ("crm.lead", "sale.order")

_CACHE = {}
DEFAULT_CACHE_SECONDS = 60


class SgcCesKpiService(models.AbstractModel):
    _name = "sgc.ces.kpi.service"
    _description = "SGC CES KPI Service"

    # ------------------------------------------------------------- caching
    @api.model
    def _cache_seconds(self):
        return self.env["sgc.ces.identity"]._param_int(
            "sgc_ces_kpi_banner.cache_seconds", DEFAULT_CACHE_SECONDS
        ) or DEFAULT_CACHE_SECONDS

    @api.model
    def _caching_enabled(self):
        """Never cache inside the test runner: the process-level cache would
        otherwise leak payloads across rolled-back transactions."""
        return not config.get("test_enable")

    @api.model
    def _cache_get(self, key):
        if not self._caching_enabled():
            return None
        entry = _CACHE.get(key)
        if not entry:
            return None
        stamp, payload = entry
        if time.time() - stamp > self._cache_seconds():
            _CACHE.pop(key, None)
            return None
        return payload

    @api.model
    def _cache_set(self, key, payload):
        if not self._caching_enabled():
            return payload
        if len(_CACHE) > 500:
            _CACHE.clear()
        _CACHE[key] = (time.time(), payload)
        return payload

    @api.model
    def invalidate_cache_for_user(self, user_id):
        for key in [k for k in _CACHE if k[1] == user_id]:
            _CACHE.pop(key, None)
        return True

    # ------------------------------------------------------------- security
    @api.model
    def _assert_can_read_user(self, user_id):
        if user_id == self.env.uid:
            return True
        identity = self.env["sgc.ces.identity"]
        if self.env.user.has_group("sgc_ces_kpi_banner.group_ces_kpi_admin"):
            return True
        if self.env.user.has_group("sgc_ces_kpi_banner.group_ces_kpi_manager"):
            if user_id in identity.managed_user_ids(self.env.user):
                return True
        raise AccessError(
            _("You are not allowed to read the CES KPI summary of another user.")
        )

    # -------------------------------------------------------- RPC method 1
    @api.model
    def get_my_ces_kpi_summary(self):
        """Summary for the calling user. Safe for every logged-in user."""
        return self._summary_for_user(self.env.user)

    # -------------------------------------------------------- RPC method 2
    @api.model
    def get_ces_kpi_summary(self, user_id):
        """Summary for another user; manager or administrator only."""
        user_id = int(user_id)
        self._assert_can_read_user(user_id)
        user = self.env["res.users"].sudo().browse(user_id).exists()
        if not user:
            return self._empty_summary()
        return self._summary_for_user(user)

    # -------------------------------------------------------- RPC method 3
    @api.model
    def get_gate_review_summary(self, gate_instance_id):
        """Reviewer-facing detail for a single gate instance."""
        instance = self.env["sgc.ces.gate.instance"].browse(int(gate_instance_id))
        instance.check_access("read")
        instance = instance.sudo()
        instance.evaluate()
        payload = instance.summary_dict()
        payload.update(
            {
                "employee_name": instance.employee_id.name or "",
                "manager_name": instance.manager_user_id.name or "",
                "plan": instance.plan_id.display_name,
                "considerations": [
                    {
                        "id": c.id,
                        "type": c.consideration_type,
                        "state": c.state,
                        "reason": c.reason or "",
                        "new_due_date": fields.Date.to_string(c.new_due_date),
                        "adjusted_target": c.adjusted_target,
                    }
                    for c in instance.consideration_ids
                ],
                "reviews": [
                    {
                        "id": r.id,
                        "state": r.state,
                        "alert_type": r.alert_type,
                        "decision": r.decision or "",
                        "scheduled": fields.Date.to_string(r.alert_scheduled_date),
                    }
                    for r in instance.review_ids
                ],
            }
        )
        return payload

    # ------------------------------------------------------ drill-down RPC
    @api.model
    def get_drilldown_action(self, kind, ref_id):
        """Return a server-built act_window. No client supplied domain is accepted.

        ``kind`` is one of ``requirement`` or ``kpi``; ``ref_id`` identifies the
        record whose *server side* domain should be opened.
        """
        if kind == "requirement":
            result = self.env["sgc.ces.gate.requirement.result"].browse(int(ref_id))
            result.check_access("read")
            action = result.sudo().action_open_drilldown()
        elif kind == "kpi":
            action = self._kpi_drilldown(int(ref_id))
        else:
            raise AccessError(_("Unsupported drill-down type."))
        if action.get("type") == "ir.actions.act_window":
            if action.get("res_model") not in DRILLDOWN_WHITELIST:
                raise AccessError(_("This drill-down target is not permitted."))
        return action

    def _kpi_drilldown(self, target_id):
        target = self.env["sgc.ces.kpi.target"].sudo().browse(target_id).exists()
        if not target:
            raise AccessError(_("Unknown KPI target."))
        registry = self.env["sgc.ces.metric.registry"]
        date_from, date_to = registry.resolve_window(
            "current_day" if target.period == "daily" else "current_month"
        )
        outcome = registry.safe_evaluate(
            target.metric_code,
            {
                "user_id": self.env.uid,
                "date_from": date_from,
                "date_to": date_to,
                "params": target.metric_params(),
                "company_ids": self.env.company.ids,
            },
        )
        if not outcome.get("res_model") or outcome.get("domain") is None:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {"type": "warning", "message": _("No safe drill-down for this KPI.")},
            }
        return {
            "type": "ir.actions.act_window",
            "name": target.name,
            "res_model": outcome["res_model"],
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "domain": outcome["domain"],
            "target": "current",
        }

    # ---------------------------------------------------------- computation
    @api.model
    def _empty_summary(self):
        return {
            "is_ces": False,
            "enabled": False,
            "baseline_pending": False,
            "user_id": self.env.uid,
            "user_name": self.env.user.name,
            "gates": [],
            "kpis": {"daily": [], "monthly": []},
            "next_action": None,
            "warnings": [],
            "generated_on": fields.Datetime.to_string(fields.Datetime.now()),
        }

    @api.model
    def _summary_for_user(self, user):
        identity = self.env["sgc.ces.identity"]
        enabled = identity._param_bool("sgc_ces_kpi_banner.banner_enabled", True)
        cache_key = ("summary", user.id, self.env.company.id)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        payload = self._empty_summary()
        payload.update(
            {
                "user_id": user.id,
                "user_name": user.name,
                "enabled": enabled,
                "is_ces": identity.is_ces_user(user),
            }
        )
        if not enabled:
            return self._cache_set(cache_key, payload)

        warnings = []
        Assignment = self.env["sgc.ces.gate.assignment"].sudo()
        pending_baseline = Assignment.search(
            [("user_id", "=", user.id), ("state", "=", "pending_baseline")], limit=1
        )
        if pending_baseline:
            payload["baseline_pending"] = True
            payload["warnings"] = [_("CES Target Assessment Pending")]
            payload["generated_on"] = fields.Datetime.to_string(fields.Datetime.now())
            return self._cache_set(cache_key, payload)

        Instance = self.env["sgc.ces.gate.instance"].sudo()
        instances = Instance.search(
            [
                ("user_id", "=", user.id),
                ("state", "in", ("active", "pending_review", "in_review", "extended")),
            ],
            order="due_date asc",
            limit=10,
        )
        instances.evaluate()
        payload["gates"] = [i.summary_dict() for i in instances]

        payload["kpis"] = {
            "daily": self._kpi_block(user, "daily"),
            "monthly": self._kpi_block(user, "monthly"),
        }

        if payload["is_ces"] and not instances:
            warnings.append(
                _("You are identified as a CES but have no active gate assignment yet.")
            )
        payload["warnings"] = warnings
        payload["next_action"] = self._next_action(payload)
        payload["generated_on"] = fields.Datetime.to_string(fields.Datetime.now())
        return self._cache_set(cache_key, payload)

    def _kpi_block(self, user, period):
        registry = self.env["sgc.ces.metric.registry"]
        targets = self.env["sgc.ces.kpi.target"].targets_for_user(user, period)
        window = "current_day" if period == "daily" else "current_month"
        date_from, date_to = registry.resolve_window(window)
        block = []
        for target in targets:
            outcome = registry.safe_evaluate(
                target.metric_code,
                {
                    "user_id": user.id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "params": target.metric_params(),
                    "company_ids": self.env.company.ids,
                },
            )
            value = outcome.get("value") or 0.0
            block.append(
                {
                    "target_id": target.id,
                    "name": target.name,
                    "metric_code": target.metric_code,
                    "unit": outcome.get("unit"),
                    "value": value,
                    "target": target.target_value,
                    "comparator": target.comparator,
                    "achieved": compare(value, target.comparator, target.target_value),
                    "progress": round(
                        progress_ratio(value, target.comparator, target.target_value) * 100.0, 1
                    ),
                    "help_text": target.help_text or "",
                    "has_drilldown": bool(outcome.get("res_model")),
                    "error": outcome.get("error") or "",
                }
            )
        return block

    # ------------------------------------------------------- next action
    @api.model
    def _next_action(self, payload):
        """Deterministic next-recommended-action.

        Strict priority order, entirely rule based - no generative text:

        1. A mandatory requirement that is not met, on the gate closest to its
           due date (earliest due date wins, then lowest progress).
        2. A weighted requirement below target on that same gate.
        3. A daily KPI below target (lowest progress first).
        4. A monthly KPI below target (lowest progress first).
        5. Nothing outstanding.
        """
        gates = sorted(
            payload.get("gates") or [], key=lambda g: (g.get("due_date") or "9999-12-31", g["id"])
        )
        for level in ("mandatory", "weighted"):
            for gate in gates:
                unmet = [
                    r
                    for r in gate.get("requirements", [])
                    if r["level"] == level and not r["achieved"]
                ]
                if not unmet:
                    continue
                unmet.sort(key=lambda r: (r["progress"], r["id"]))
                requirement = unmet[0]
                return {
                    "kind": "requirement",
                    "ref_id": requirement["id"],
                    "gate_id": gate["id"],
                    "label": _("%(name)s: %(value)s of %(target)s")
                    % {
                        "name": requirement["name"],
                        "value": self._format_number(requirement["value"], requirement["unit"]),
                        "target": self._format_number(requirement["target"], requirement["unit"]),
                    },
                    "reason": _("Gate '%(gate)s' is due %(due)s.")
                    % {"gate": gate["name"], "due": gate.get("effective_due_date") or ""},
                    "has_drilldown": requirement["has_drilldown"],
                }
        for period in ("daily", "monthly"):
            pending = [k for k in payload["kpis"].get(period, []) if not k["achieved"]]
            if pending:
                pending.sort(key=lambda k: (k["progress"], k["target_id"]))
                kpi = pending[0]
                return {
                    "kind": "kpi",
                    "ref_id": kpi["target_id"],
                    "gate_id": None,
                    "label": _("%(name)s: %(value)s of %(target)s")
                    % {
                        "name": kpi["name"],
                        "value": self._format_number(kpi["value"], kpi["unit"]),
                        "target": self._format_number(kpi["target"], kpi["unit"]),
                    },
                    "reason": _("%s target not reached yet.")
                    % (_("Today's") if period == "daily" else _("This month's")),
                    "has_drilldown": kpi["has_drilldown"],
                }
        return {
            "kind": "none",
            "ref_id": None,
            "gate_id": None,
            "label": _("Everything is on target."),
            "reason": "",
            "has_drilldown": False,
        }

    @api.model
    def _format_number(self, value, unit):
        if unit == "percent":
            return "%.1f%%" % (value or 0.0)
        if unit == "currency":
            # symbol removed - display only count
 symbol = ""
            return "%s%s" % (symbol, "{:,.0f}".format(value or 0.0))
        return "{:,.0f}".format(value or 0.0)

    # ------------------------------------------------ configuration health
    @api.model
    def configuration_health(self):
        """Surface known data-quality blockers as visible warnings."""
        identity = self.env["sgc.ces.identity"]
        issues = []
        job = identity._resolve_ces_job()
        if not job:
            issues.append(
                {
                    "level": "error",
                    "code": "ces_job_missing",
                    "message": _("No CES hr.job could be resolved. Set "
                                 "sgc_ces_kpi_banner.ces_job_id or ces_job_name."),
                }
            )
        if not identity.proposal_stage():
            issues.append(
                {"level": "warning", "code": "proposal_stage_missing",
                 "message": _("No Proposal CRM stage could be resolved.")}
            )
        SaleOrder = self.env["sale.order"].sudo()
        signed = SaleOrder.search_count([("signed_on", "!=", False)])
        if not signed:
            issues.append(
                {
                    "level": "warning",
                    "code": "no_signed_orders",
                    "message": _("No sale order has ever been signed natively, so the "
                                 "signed-proposal metric reads zero. Either enable the native "
                                 "online-signature flow or build a write-back from your "
                                 "e-signature provider."),
                }
            )
        total_orders = SaleOrder.search_count([])
        linked = SaleOrder.search_count([("opportunity_id", "!=", False)])
        if total_orders and linked / total_orders < 0.5:
            issues.append(
                {
                    "level": "warning",
                    "code": "weak_opportunity_link",
                    "message": _("Only %(linked)s of %(total)s sale orders are linked to an "
                                 "opportunity, which limits pipeline-to-payment attribution.")
                    % {"linked": linked, "total": total_orders},
                }
            )
        if "x_days_since_activity" in self.env["crm.lead"]._fields:
            issues.append(
                {
                    "level": "info",
                    "code": "dead_staleness_field",
                    "message": _("x_days_since_activity exists but is never written by any "
                                 "code path; it is excluded from the staleness metric on "
                                 "purpose."),
                }
            )
        assignments = self.env["sgc.ces.gate.assignment"].sudo().search_count(
            [("state", "=", "active")]
        )
        if not assignments:
            issues.append(
                {"level": "info", "code": "no_active_assignment",
                 "message": _("No gate assignment is active yet. Nothing is being measured.")}
            )
        return issues
