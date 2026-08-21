# -*- coding: utf-8 -*-
{
    "name": "SGC - AI Nurture Orchestrator",
    "version": "19.0.1.0.0",
    "category": "CRM",
    "summary": "Automates the WhatsApp/email nurture sequence for leads flagged with a nurture activity",
    "description": """
SGC AI Nurture Orchestrator
============================
Executes, automatically, what `sgc_proposal_nurture` currently only flags
for a human to do by hand: a bounded, AI-drafted WhatsApp + email touch
sequence for a lead, gated entirely behind an assigned activity.

Phase 0/1 scope (this build): the full sequence/touch state machine,
centralized stop/pause matrix, business-hours scheduler, and AI drafting
+ deterministic validation all run for real -- but every send is
**dry-run only**. A drafted touch is posted as an internal note on the
lead's chatter for review; nothing is queued on `whatsmeow.message` or
`mail.mail`, and no lead is ever contacted. Flipping `dry_run` off per
channel is a deliberate later phase, not a default here.

Fields/models added:
    * sgc.nurture.sequence -- one row per lead enrollment, owns the
      touch counter, schedule, and status.
    * sgc.nurture.touch -- one row per planned/drafted/sent touch,
      for observability (what was drafted, when, by which model, at
      what cost, and what happened to it).

Enrollment trigger (v1, deliberately narrow): crm.lead.x_nurture_state
turning 'pending' -- the exact flag `sgc_proposal_nurture`'s Rule B
already sets today for a lead stalled 3+ days in Proposal. No new CRM
automation rule is introduced by this module; it only starts executing
what already gets flagged.

Stop/pause matrix (centralized in
`sgc.nurture.sequence._evaluate_stop_conditions`, not scattered across
the cron): WhatsApp reply, email reply, meeting booked, opportunity
won/lost, lead archived, manual pause/stop. See the model docstring for
the full table and what's still a TODO (bounce/invalid-number detection,
duplicate-lead detection -- both need signals this build doesn't wire
up yet).

Handoff on response reassigns the lead across the whole Sales team
(crm.team.member), weighted by `sgc_crm_dashboard`'s existing leaderboard
score -- see the model docstring for why this is flagged as a Phase 4
concern, not activated by default here.
    """,
    "author": "SGC Tech AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "crm",
        "calendar",
        "sgc_proposal_nurture",
        "sgc_lead_scoring",
        "sgc_sales_playbook",
        "sgc_crm_dashboard",
        "whatsmeow",
        "whatsmeow_template",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/nurture_stop_automations.xml",
        "views/sgc_nurture_sequence_views.xml",
        "views/sgc_nurture_touch_views.xml",
        "views/crm_lead_views.xml",
        "views/menu.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
