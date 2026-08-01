# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, models

# Unlike the field-level duck-typing used elsewhere in this repo (e.g.
# sgc_crm_ai_compat), inheriting an abstract model by name is resolved at
# registry-build time for every installed module together — if
# 'sgc.kpi.provider' didn't exist, Odoo would fail to load. sgc_sales_playbook
# therefore hard-depends on sgc_executive_dashboard in its manifest.


class SgcProviderPipelineQualification(models.AbstractModel):
    _name = "sgc.provider.pipeline.qualification"
    _inherit = "sgc.kpi.provider"
    _description = "SGC Provider: Pipeline Qualification (Playbook Gates)"

    _sgc_module = "sgc_sales_playbook"
    _sgc_label = "Pipeline Qualification"
    _sgc_icon = "fa-check-square-o"
    _sgc_accent = "violet"
    _sgc_sequence = 6
    _sgc_pitch = "Are deals being properly qualified before they advance? Gate pass rate, stalled deals, objection conversion."

    @api.model
    def _sgc_collect(self, ctx):
        """KPI definitions (numerator / denominator / window / exclusions):

        gate_pass_rate: numerator = crm.lead where x_gate_status ==
        'qualified'; denominator = crm.lead where type='opportunity',
        active=True, company in ctx, stage_id.sequence >= 7 (Meeting
        Booked and later — the playbook's gate check happens before
        Proposal). Window: point-in-time snapshot, NOT scoped to
        ctx['dt_from']/dt_to — there is no historical gate-pass table to
        query a date range against. None (not 0%) when the denominator is
        0. Also emitted split by provenance (gate_pass_rate_ai /
        gate_pass_rate_human, via the 4 per-field x_gate_*_provenance
        selections — see crm.lead._get_gate_provenance_domain()) so a gate
        passing mostly on AI-inferred answers is visible to whoever asks.

        stalled_deals_count: crm.lead where type='opportunity', active=True,
        company in ctx, date_last_stage_update set and <= ctx['dt_to'] - 21
        days. Raw count, not a rate — no denominator to guard.

        objection_conversion_rate: numerator = sgc.lead.objection where
        resulted_in_meeting=True; denominator = sgc.lead.objection created
        on/after ctx['dt_from'] (this one IS date-windowed, unlike
        gate_pass_rate — objections are logged events with a create_date,
        gate status is a point-in-time field). None when 0 objections in
        the window.
        """
        kpis, charts = [], []
        Lead = self.env["crm.lead"].sudo()

        # "Deals that should be gated": anything at or past the Proposal
        # stage, still open. Meeting Booked is the stage immediately before
        # Proposal (playbook: gate check happens before advancing).
        base_dom = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("company_id", "in", ctx["company_ids"]),
            ("stage_id.sequence", ">=", 7),  # Meeting Booked (7) and later
        ]
        gateable = self._sgc_count("crm.lead", base_dom)
        gate_pass_rate = None
        gate_pass_rate_ai = None
        gate_pass_rate_human = None
        gateable_ai = gateable_human = 0
        if gateable:
            qualified = self._sgc_count("crm.lead", base_dom + [("x_gate_status", "=", "qualified")])
            gate_pass_rate = qualified / gateable * 100.0

            ai_dom = base_dom + Lead._get_gate_provenance_domain("ai")
            human_dom = base_dom + Lead._get_gate_provenance_domain("human")
            gateable_ai = self._sgc_count("crm.lead", ai_dom)
            if gateable_ai:
                ai_qualified = self._sgc_count("crm.lead", ai_dom + [("x_gate_status", "=", "qualified")])
                gate_pass_rate_ai = ai_qualified / gateable_ai * 100.0
            gateable_human = self._sgc_count("crm.lead", human_dom)
            if gateable_human:
                human_qualified = self._sgc_count("crm.lead", human_dom + [("x_gate_status", "=", "qualified")])
                gate_pass_rate_human = human_qualified / gateable_human * 100.0

        stalled_dom = [
            ("type", "=", "opportunity"),
            ("active", "=", True),
            ("company_id", "in", ctx["company_ids"]),
            ("date_last_stage_update", "!=", False),
            ("date_last_stage_update", "<=", ctx["dt_to"] - timedelta(days=21)),
        ]
        stalled_count = self._sgc_count("crm.lead", stalled_dom)

        Objection = self.env["sgc.lead.objection"].sudo()
        total_objections = Objection.search_count([("create_date", ">=", ctx["dt_from"])])
        objection_conversion_rate = None
        if total_objections:
            won_objections = Objection.search_count(
                [("create_date", ">=", ctx["dt_from"]), ("resulted_in_meeting", "=", True)]
            )
            objection_conversion_rate = won_objections / total_objections * 100.0

        kpis += [
            self._sgc_kpi(
                "gate_pass_rate",
                _("Gate Pass Rate"),
                gate_pass_rate,
                format="percent",
                icon="fa-check-square-o",
                accent="violet",
                hint=_("Meeting Booked+ deals with all 4 exit criteria answered (n=%s)") % gateable,
            ),
            self._sgc_kpi(
                "gate_pass_rate_ai",
                _("Gate Pass Rate (AI-Extracted)"),
                gate_pass_rate_ai,
                format="percent",
                icon="fa-check-square-o",
                accent="violet",
                hint=_("Same population, answers copied from an AI transcript summary (n=%s)") % gateable_ai,
            ),
            self._sgc_kpi(
                "gate_pass_rate_human",
                _("Gate Pass Rate (Rep-Typed)"),
                gate_pass_rate_human,
                format="percent",
                icon="fa-check-square-o",
                accent="violet",
                hint=_("Same population, answers typed directly by the rep (n=%s)") % gateable_human,
            ),
            self._sgc_kpi(
                "stalled_deals_count",
                _("Stalled Deals"),
                stalled_count,
                icon="fa-hourglass-half",
                accent="rose",
                hint=_("No stage movement in 3+ weeks"),
            ),
            self._sgc_kpi(
                "objection_conversion_rate",
                _("Objection → Meeting Rate"),
                objection_conversion_rate,
                format="percent",
                icon="fa-comments-o",
                accent="amber",
                hint=_("n=%s objections logged this period") % total_objections,
            ),
        ]
        return {"kpis": kpis, "charts": charts}
