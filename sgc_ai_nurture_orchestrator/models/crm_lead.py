# -*- coding: utf-8 -*-
from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    nurture_sequence_ids = fields.One2many("sgc.nurture.sequence", "lead_id")
    nurture_sequence_count = fields.Integer(compute="_compute_nurture_sequence_count")
    active_nurture_sequence_id = fields.Many2one(
        "sgc.nurture.sequence", compute="_compute_active_nurture_sequence_id",
    )

    def _compute_nurture_sequence_count(self):
        for lead in self:
            lead.nurture_sequence_count = len(lead.nurture_sequence_ids)

    def _compute_active_nurture_sequence_id(self):
        live = ("scheduled", "active", "paused")
        for lead in self:
            lead.active_nurture_sequence_id = lead.nurture_sequence_ids.filtered(
                lambda s: s.status in live)[:1]

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
