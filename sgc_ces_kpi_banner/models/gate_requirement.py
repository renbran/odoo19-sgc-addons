# -*- coding: utf-8 -*-
"""Generic gate requirement: metric code + comparator + target + window.

Nothing executable is stored. ``metric_code`` is a closed selection resolved
through ``models/metric_registry.py``; every tuning knob is a typed scalar
field, and the provider decides what to do with it.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .metric_registry import COMPARATOR_SELECTION, METRIC_SELECTION, WINDOW_SELECTION


class SgcCesGateRequirement(models.Model):
    _name = "sgc.ces.gate.requirement"
    _description = "SGC CES Gate Requirement"
    _order = "template_id, sequence, id"

    name = fields.Char(required=True)
    template_id = fields.Many2one(
        "sgc.ces.gate.template", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="template_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    metric_code = fields.Selection(METRIC_SELECTION, required=True)
    comparator = fields.Selection(COMPARATOR_SELECTION, default=">=", required=True)
    target_value = fields.Float(required=True, digits=(16, 2))
    measurement_window = fields.Selection(
        WINDOW_SELECTION, default="since_gate_start", required=True
    )
    window_days = fields.Integer(
        default=30, help="Only used when the measurement window is a rolling window."
    )

    level = fields.Selection(
        [
            ("mandatory", "Mandatory"),
            ("weighted", "Weighted"),
            ("informational", "Informational"),
        ],
        default="mandatory",
        required=True,
        help="Mandatory requirements can never be averaged away by other results.",
    )
    weight = fields.Float(default=1.0, help="Relative weight inside the weighted score.")

    # -- typed metric parameters (no expressions, no domains) ----------------
    min_expected_revenue = fields.Float(help="Pipeline: ignore opportunities below this amount.")
    probability_min = fields.Float(help="Pipeline: minimum win probability (0-100).")
    proposal_only = fields.Boolean(help="Restrict to the configured Proposal stage.")
    include_won = fields.Boolean(help="Pipeline: count Won opportunities as pipeline.")
    date_field = fields.Selection(
        [
            ("create_date", "Creation date"),
            ("date_open", "Assignment date"),
            ("date_last_stage_update", "Last stage change"),
        ],
        default="create_date",
        help="Pipeline: which date the measurement window filters on.",
    )

    staleness_field = fields.Selection(
        [
            ("date_last_stage_update", "Last stage change (native, recommended)"),
            ("x_last_activity_date", "Last enrichment run (x_last_activity_date - see help)"),
        ],
        default="date_last_stage_update",
        help="x_last_activity_date is only written by the Apollo/Hunter/LLM enrichment "
             "crons, so it reflects the last enrichment run, not the last customer touch. "
             "x_days_since_activity is deliberately not offered: it is declared but never "
             "written by any code path.",
    )
    stale_days = fields.Integer(default=45, help="Days without movement before an opportunity is stale.")
    warn_days = fields.Integer(default=30, help="Days without movement before an opportunity is at risk.")

    signature_strategy = fields.Selection(
        [
            ("native", "Native Odoo quotation signature (recommended)"),
            ("external", "External e-signature envelope fields"),
            ("combined", "Either source"),
        ],
        default="native",
        help="The external envelope fields (Zoho Sign naming) currently have no "
             "write-back integration, so that strategy reads zero until one exists.",
    )
    require_signature_only = fields.Boolean(
        help="Only count orders that actually requested a signature.")
    order_states = fields.Char(
        default="sale", help="Comma separated sale.order states that qualify.")

    qualifying_payment_mode = fields.Selection(
        [
            ("paid", "Fully paid invoices only"),
            ("paid_partial", "Fully or partially paid"),
            ("paid_inclusive", "Paid, partial or in payment"),
        ],
        default="paid",
    )
    require_opportunity = fields.Boolean(
        help="Only count orders linked to an opportunity. Currently a small subset of orders.")

    help_text = fields.Text(help="Shown to the CES user in the banner tooltip.")

    @api.constrains("weight")
    def _check_weight(self):
        for req in self:
            if req.level == "weighted" and req.weight <= 0:
                raise ValidationError(_("A weighted requirement must have a positive weight."))

    @api.constrains("window_days", "stale_days", "warn_days")
    def _check_days(self):
        for req in self:
            if req.measurement_window == "rolling_days" and req.window_days < 1:
                raise ValidationError(_("A rolling window must be at least one day long."))
            if req.stale_days < 1:
                raise ValidationError(_("Stale days must be at least 1."))
            if req.warn_days < 0:
                raise ValidationError(_("Warning days cannot be negative."))

    @api.constrains("order_states")
    def _check_order_states(self):
        allowed = set(dict(self.env["sale.order"]._fields["state"].selection))
        for req in self:
            if not req.order_states:
                continue
            for state in req.order_states.split(","):
                state = state.strip()
                if state and state not in allowed:
                    raise ValidationError(_("'%s' is not a valid sale order state.") % state)

    def metric_params(self):
        """Return the typed parameter dict handed to the metric provider."""
        self.ensure_one()
        return {
            "min_expected_revenue": self.min_expected_revenue,
            "probability_min": self.probability_min,
            "proposal_only": self.proposal_only,
            "include_won": self.include_won,
            "date_field": self.date_field,
            "staleness_field": self.staleness_field,
            "stale_days": self.stale_days,
            "warn_days": self.warn_days,
            "signature_strategy": self.signature_strategy,
            "require_signature_only": self.require_signature_only,
            "order_states": self.order_states,
            "qualifying_payment_mode": self.qualifying_payment_mode,
            "require_opportunity": self.require_opportunity,
            "window_days": self.window_days,
        }
