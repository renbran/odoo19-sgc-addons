# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    nurture_sequence_ids = fields.One2many("sgc.nurture.sequence", "lead_id")
    nurture_sequence_count = fields.Integer(compute="_compute_nurture_sequence_count")
    active_nurture_sequence_id = fields.Many2one(
        "sgc.nurture.sequence", compute="_compute_active_nurture_sequence_id",
    )
    nurture_eligible = fields.Boolean(
        compute="_compute_nurture_eligible",
        help="x_nurture_state is 'pending' (sgc_proposal_nurture's flag) and "
             "no live sequence already exists for this lead. Drives the "
             "'Start Nurture Sequence' button's visibility -- nothing about "
             "eligibility starts a sequence on its own; a person still has "
             "to click the button.",
    )

    @api.depends("x_nurture_state", "nurture_sequence_ids.status")
    def _compute_nurture_eligible(self):
        live = ("scheduled", "active", "paused")
        for lead in self:
            lead.nurture_eligible = (
                lead.x_nurture_state == "pending"
                and not lead.nurture_sequence_ids.filtered(lambda s: s.status in live)
            )

    def _compute_nurture_sequence_count(self):
        for lead in self:
            lead.nurture_sequence_count = len(lead.nurture_sequence_ids)

    def _compute_active_nurture_sequence_id(self):
        live = ("scheduled", "active", "paused")
        for lead in self:
            lead.active_nurture_sequence_id = lead.nurture_sequence_ids.filtered(
                lambda s: s.status in live)[:1]

    def action_start_nurture(self):
        """The ONLY way a nurture sequence gets created -- a person clicking
        this button. There is deliberately no cron or automation rule that
        calls this; enrollment used to sweep every eligible lead on a timer,
        which is exactly what this button replaces (see PLAN.md and the
        sgc_ai_nurture_orchestrator README for why: nothing in this module
        may act on a lead without an explicit human trigger).
        """
        self.ensure_one()
        if not self.nurture_eligible:
            raise UserError(_(
                "This lead isn't eligible for nurture right now -- either "
                "there's no pending nurture flag, or a sequence is already "
                "running."
            ))
        Sequence = self.env["sgc.nurture.sequence"].sudo()
        activity = self.env["mail.activity"].search([
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", self.id),
            ("summary", "=", "Generate proposal-nurture sequence"),
        ], limit=1)
        seq = Sequence.create({
            "lead_id": self.id,
            "trigger_activity_id": activity.id or False,
            "status": "active",
        })
        seq.message_post(body=_(
            "Nurture sequence started by %s. No touch has been drafted yet "
            "-- use \"Draft Next Touch\" on the sequence to generate one.",
            self.env.user.name,
        ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Nurture Sequence"),
            "res_model": "sgc.nurture.sequence",
            "res_id": seq.id,
            "view_mode": "form",
            "target": "current",
        }

    # -- called from base.automation rules in data/nurture_stop_automations.xml
    # (mirrors sgc_proposal_nurture's own C1/C2/C3 style: the automation
    # record supplies the trigger, this method supplies the one line of
    # logic, so the stop reasoning itself still lives in one place --
    # sgc.nurture.sequence._evaluate_stop_conditions / _apply_stop.)
    def _sgc_nurture_on_message_received(self):
        for lead in self:
            seq = lead.active_nurture_sequence_id
            if seq and seq.status == "active":
                seq._register_engagement("strong")
                seq._apply_stop("Lead replied by email.", "email_reply")

    def _sgc_nurture_on_meeting_booked(self):
        for lead in self:
            seq = lead.active_nurture_sequence_id
            if seq and seq.status == "active":
                seq._register_engagement("strong")
                seq._apply_stop("Meeting booked.", "meeting_booked")

    def _sgc_nurture_on_lead_closed(self):
        """Won/Lost/archived closes the sequence promptly instead of
        waiting for the next cron tick to notice via
        `_evaluate_stop_conditions` -- that check still runs regardless
        (it's what actually protects a live send later), this just keeps
        `status` from sitting stale as 'active' for up to 2 days.
        """
        for lead in self:
            seq = lead.active_nurture_sequence_id
            if not seq or seq.status != "active":
                continue
            should_stop, reason, event = seq._evaluate_stop_conditions()
            if should_stop:
                seq._apply_stop(reason, event)
