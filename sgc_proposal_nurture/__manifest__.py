# -*- coding: utf-8 -*-
{
    "name": "SGC - Proposal Nurture Automation",
    "version": "19.0.1.0.0",
    "category": "CRM",
    "summary": "Flags proposal-stage leads stalled 3+ days for manual nurture-campaign generation in Claude Code",
    "description": """
SGC Proposal Nurture Automation
================================
Tracks how long a lead has sat in the "Proposal" stage and, after 3 days
with no movement, flags it internally (chatter note + activity) for a rep
to generate a nurture campaign via Claude Code's /nurture-queue skill.

This module never sends email itself — every action is an internal note
or a scheduled activity. All outbound copy is generated locally (in the
marketing-and-lead-generation Claude Code project) and sent manually by a
human afterwards.

Fields added to crm.lead:
    * x_proposal_entered_on — stamped once when a lead first enters Proposal
    * x_nurture_state — pending / generated / sent / stopped
    * x_nurture_flagged_on — stamped when the 3-day flag fires

Automation rules:
    * Rule A — stamps x_proposal_entered_on on entering Proposal (once only)
    * Rule B — 3 days after x_proposal_entered_on, flags the lead pending
    * Rule C1/C2 — clears the flag if the lead moves stage or a reply arrives
    """,
    "author": "SGC Tech AI",
    "license": "LGPL-3",
    "depends": ["base", "crm", "mail", "base_automation"],
    "data": [
        "data/automation_rules.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
