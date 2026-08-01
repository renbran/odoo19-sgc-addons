# -*- coding: utf-8 -*-
from odoo import models, fields, api

# Mr. Miyagi reframe cheat sheet (playbook Phase 2). Keyed by objection_type
# selection value so "Suggest Reframe" is a pure lookup, no LLM call needed.
REFRAME_SUGGESTIONS = {
    "already_have_system": (
        "I hear you. In fact, that's exactly why I'm calling. We work with "
        "[system] users every day — usually to bridge gaps in areas the "
        "standard setup wasn't designed for. Let's do 15 minutes to see if "
        "there's a gap worth closing."
    ),
    "not_interested": (
        "I hear you, and I respect your time. Quick question — are you "
        "already compliant/set up for this, or is it on your radar? If "
        "you're already set, I'll leave you alone entirely."
    ),
    "send_email": (
        "I will — and I'll include a gap analysis specific to your "
        "situation. But the reason I'm calling instead of emailing is that "
        "every company's setup is different. A 3-minute conversation saves "
        "30 minutes of back-and-forth. Got 3 minutes now?"
    ),
    "no_budget": (
        "I hear you. The diagnostic is free. You'll know exactly what the "
        "gap is. If it's small, walk away. If it's big, you can plan for "
        "it. That's fair, right?"
    ),
    "other": "",
}


class SgcLeadObjection(models.Model):
    _name = "sgc.lead.objection"
    _description = "SGC Lead Objection Log (Mr. Miyagi Method tracking)"
    _order = "create_date desc"

    lead_id = fields.Many2one(
        "crm.lead", string="Opportunity", required=True, ondelete="cascade", index=True
    )
    objection_type = fields.Selection(
        [
            ("already_have_system", "“We already have a system”"),
            ("not_interested", "“We're not interested”"),
            ("send_email", "“Send me an email”"),
            ("no_budget", "“No budget”"),
            ("other", "Other"),
        ],
        string="Objection",
        required=True,
    )
    reframe_used = fields.Text(string="Reframe Used")
    resulted_in_meeting = fields.Boolean(string="Resulted in Meeting")

    @api.onchange("objection_type")
    def _onchange_objection_type_suggest_reframe(self):
        for rec in self:
            if rec.objection_type and not rec.reframe_used:
                rec.reframe_used = REFRAME_SUGGESTIONS.get(rec.objection_type, "")

    def action_suggest_reframe(self):
        for rec in self:
            if rec.objection_type:
                rec.reframe_used = REFRAME_SUGGESTIONS.get(rec.objection_type, "")
