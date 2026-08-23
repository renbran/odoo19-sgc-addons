# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # crm.lead._merge_opportunity(auto_unlink=False) does NOT archive the
    # absorbed records on its own — confirmed empirically in scratch: with
    # auto_unlink=False the tail leads stay active=True and fully visible.
    # unlink() is a real hard delete (no active-field override), so
    # reversibility has to be implemented here explicitly: the merge runner
    # sets these two fields on the absorbed lead and archives it itself.
    x_dedup_merged_into_id = fields.Many2one(
        'crm.lead', string='Merged Into (Dedup)', readonly=True, copy=False, index=True)
    x_dedup_merged_on = fields.Datetime(string='Merged On (Dedup)', readonly=True, copy=False)

    def _sort_by_confidence_level(self, reverse=False):
        """SGC master-selection rule for merges: highest pipeline stage wins;
        if tied on stage, the oldest record (create_date) wins. Nothing else
        — no type/active check, no probability comparison, no completeness
        scoring. `-id` is kept only as a final tiebreak for determinism when
        two leads share both stage and create_date exactly; it carries no
        business meaning.

        NOTE: this method is also used by website_crm (visitor lead merge)
        and website_crm_sms (phone-match lead pick), not only by
        crm.lead._merge_opportunity — the same ranking now applies there too.
        """
        def opps_key(lead):
            create_ts = lead.create_date.timestamp() if lead.create_date else 0
            return (
                lead.stage_id.sequence,
                -create_ts,
                -lead._origin.id,
            )
        return self.sorted(key=opps_key, reverse=reverse)

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._check_dedup_blocklist_hit()
        return leads

    def write(self, vals):
        res = super().write(vals)
        if {'email_from', 'email_normalized', 'phone', 'phone_sanitized', 'x_mobile_phone'} & vals.keys():
            self._check_dedup_blocklist_hit()
        return res

    def _check_dedup_blocklist_hit(self):
        """Flag (never block) leads whose email/phone matches a known
        intermediary identity, so data entry can be corrected at the source.
        Ingestion is automated/external and must not be interrupted; this
        only posts a chatter warning for manual follow-up.
        """
        Blocklist = self.env['crm.lead.dedup.blocklist'].sudo()
        phone_values = {v for v in self.mapped('phone_sanitized') if v}
        phone_values |= {v for v in self.mapped('x_mobile_phone') if v}
        email_values = {v for v in self.mapped('email_normalized') if v}
        if not phone_values and not email_values:
            return
        hits = Blocklist.search([
            '|',
            '&', ('field_type', '=', 'phone'), ('value', 'in', list(phone_values)),
            '&', ('field_type', '=', 'email'), ('value', 'in', list(email_values)),
        ])
        if not hits:
            return
        hit_phones = set(hits.filtered(lambda b: b.field_type == 'phone').mapped('value'))
        hit_emails = set(hits.filtered(lambda b: b.field_type == 'email').mapped('value'))
        for lead in self:
            matched = []
            if lead.phone_sanitized in hit_phones:
                matched.append(lead.phone_sanitized)
            if lead.x_mobile_phone in hit_phones:
                matched.append(lead.x_mobile_phone)
            if lead.email_normalized in hit_emails:
                matched.append(lead.email_normalized)
            if matched:
                lead.message_post(
                    body=(
                        "Dedup guard: this lead's contact value(s) %s match a known "
                        "intermediary identity (broker/agency switchboard, not a "
                        "distinct customer). Verify the actual customer contact "
                        "before this record is used for outreach or merge."
                    ) % ", ".join(matched),
                    subtype_xmlid='mail.mt_note',
                )
