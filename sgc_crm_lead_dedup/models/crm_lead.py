# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.addons.crm.models.crm_lead import CRM_LEAD_FIELDS_TO_MERGE


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
        """SGC master-selection rule for merges.

        Odoo's stock key ranks (not lost, is_opportunity, stage.sequence,
        probability, id) — meaning an inactive-but-'won' lead can outrank an
        active opportunity sitting deep in the pipeline. For this dataset the
        record sales is actually working must survive, so stage progression
        is promoted above the type/active check, raw probability is replaced
        by "was it set by a human" (automated scoring is noise, not a basis
        for picking the surviving customer record), and ties are broken by
        oldest create_date, then most complete record, then lowest id.

        NOTE: this method is also used by website_crm (visitor lead merge)
        and website_crm_sms (phone-match lead pick), not only by
        crm.lead._merge_opportunity — the same ranking now applies there too.
        """
        def opps_key(lead):
            # Some SGC customizations remove/replace stock crm.lead fields
            # (e.g. 'title' does not exist in this install), so guard against
            # KeyError rather than assuming CRM_LEAD_FIELDS_TO_MERGE is intact.
            completeness = sum(1 for fname in CRM_LEAD_FIELDS_TO_MERGE if fname in lead._fields and lead[fname])
            create_ts = lead.create_date.timestamp() if lead.create_date else 0
            return (
                lead.stage_id.sequence,
                lead.type == 'opportunity',
                not lead.is_automated_probability,
                -create_ts,
                completeness,
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
