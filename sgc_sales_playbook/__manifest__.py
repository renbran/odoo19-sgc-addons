# -*- coding: utf-8 -*-
{
    "name": "SGC - Sales Playbook (Lead Gating & Qualification)",
    "version": "19.0.1.2.0",
    "category": "CRM",
    "summary": "Gates the Proposal stage behind Verifiable Buyer Exit Criteria and tracks SDR discovery/objection handling",
    "description": """
SGC Sales Playbook — Lead Gating & Qualification
=================================================
Implements the SGC Four-Video Sales Playbook's qualification discipline
directly in the CRM pipeline:

* Verifiable Buyer Exit Criteria — 4 gate questions (problem, cost of
  inaction, approver, timeline) that hard-block a deal from entering the
  Proposal stage until answered. Sales Managers can override with a
  logged reason.
* Pre-call research capture — Tier 1/2/3 pain-signal fields, non-blocking.
* Objection tracking — structured log of objections raised and the
  Mr. Miyagi reframe used, with canned-response suggestions.
* Pipeline discipline — weekly gate-compliance review and a dead-lead
  cleanup pass for leads stalled in "No Answer"/"Not Interested" without
  a lost reason (dry-run/log-only by default — see README before enabling
  auto-archive on a live database).
* Daily lead distribution — tops up each SDR's "New"-stage queue to a
  configurable target (default 60) from the Administrator's New-stage
  pool, Monday-Friday only. SDR pool = the configured team's members
  minus the team leader minus Administrator. Dry-run/CSV-only by default
  — see README before enabling live reassignment.
* Follow Up stage escalation — business-day timer on every Follow Up
  lead: day 2+ notification (email + Odoo activity), day 4+ final
  warning, day 5+ random redistribution to a different SDR (never back
  to the same owner) with the stage reset to New. Dry-run/CSV-only by
  default — see README before enabling live notifications/reassignment.
* A static playbook cheat-sheet reference reachable from the CRM menu.

Builds on top of sgc_lead_scoring's existing BANT fields and the
stage-dwell automation pattern proven by sgc_proposal_nurture. Does not
duplicate either.
    """,
    "author": "SGC Tech AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "base",
        "crm",
        "mail",
        "sgc_lead_scoring",
        "sgc_executive_dashboard",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/sgc_lead_objection_security.xml",
        "data/lost_reason_data.xml",
        "data/ir_cron_data.xml",
        "views/playbook_cheat_sheet.xml",
        "views/crm_lead_views.xml",
        "views/lead_objection_views.xml",
        "views/gate_override_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
