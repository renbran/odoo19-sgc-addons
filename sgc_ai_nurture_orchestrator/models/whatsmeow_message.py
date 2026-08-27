# -*- coding: utf-8 -*-
"""Inbound-WhatsApp-reply stop trigger.

whatsmeow.message has no crm.lead link of its own -- it only knows a
partner_id (when the inbound webhook resolved one) and a raw phone digit
string. Matching against an active nurture sequence therefore tries the
partner first (cheap, exact) and falls back to a loose phone-suffix
compare (a lead's stored number and the number WhatsApp reports for the
same contact don't always agree on a country-code prefix).
"""
from odoo import api, models

_PHONE_SUFFIX_LEN = 9  # enough digits to disambiguate within one country


def _digits(value):
    return "".join(ch for ch in (value or "") if ch.isdigit())


class WhatsmeowMessage(models.Model):
    _inherit = "whatsmeow.message"

    @api.model_create_multi
    def create(self, vals_list):
        messages = super().create(vals_list)
        inbound = messages.filtered(lambda m: m.direction == "in")
        if inbound:
            inbound._sgc_nurture_check_reply()
        return messages

    def _sgc_nurture_check_reply(self):
        live_statuses = ("scheduled", "active", "paused")
        for message in self:
            lead = self._sgc_nurture_find_lead(message)
            if not lead:
                continue
            seq = lead.nurture_sequence_ids.filtered(
                lambda s: s.status in live_statuses)[:1]
            if seq and seq.status == "active":
                seq._register_engagement("strong")
                seq._apply_stop("Lead replied on WhatsApp.", "wa_reply")

    def _sgc_nurture_find_lead(self, message):
        Lead = self.env["crm.lead"].sudo()
        live_domain = [
            ("active", "=", True),
            ("nurture_sequence_ids.status", "in", ("scheduled", "active", "paused")),
        ]
        # Scoped to leads with a live sequence from the start -- a partner
        # can have other, unrelated leads (won, lost, never nurtured), and
        # matching one of those instead would silently miss the real reply.
        if message.partner_id:
            lead = Lead.search(
                [("partner_id", "=", message.partner_id.id)] + live_domain, limit=1)
            if lead:
                return lead

        suffix = _digits(message.phone)[-_PHONE_SUFFIX_LEN:]
        if not suffix:
            return Lead.browse()
        # No indexed way to search "ends with" efficiently across crm_lead's
        # phone/mobile columns, and this only runs once per inbound message
        # (not in the cron's hot path), so a bounded scan is acceptable --
        # bounded to leads that actually have a live sequence, not all leads.
        candidates = Lead.search(live_domain)
        for lead in candidates:
            lead_suffixes = (
                _digits(lead.phone)[-_PHONE_SUFFIX_LEN:],
                _digits(getattr(lead, "mobile", False))[-_PHONE_SUFFIX_LEN:],
            )
            if suffix in lead_suffixes:
                return lead
        return Lead.browse()
