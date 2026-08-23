# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLeadDedupBlocklist(models.Model):
    _name = 'crm.lead.dedup.blocklist'
    _description = 'CRM Lead Dedup - Intermediary Identity Blocklist'
    _rec_name = 'value'
    _order = 'lead_count desc'

    value = fields.Char(required=True, index=True)
    field_type = fields.Selection([
        ('phone', 'Phone / Mobile'),
        ('email', 'Email'),
    ], required=True, index=True)
    lead_count = fields.Integer('Distinct Lead Count')
    source = fields.Selection([
        ('frequency', 'Frequency Threshold'),
        ('literal', 'Known Invalid Literal'),
        ('manual', 'Manual'),
    ], default='frequency', required=True)
    active = fields.Boolean(default=True)
    last_refreshed = fields.Datetime()

    _value_type_uniq = models.Constraint(
        'unique(value, field_type)',
        'This value is already blocklisted for this field type.',
    )

    @api.model
    def _get_thresholds(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'phone': int(ICP.get_param('sgc_crm_lead_dedup.phone_threshold', 10)),
            'email': int(ICP.get_param('sgc_crm_lead_dedup.email_threshold', 10)),
        }

    @api.model
    def _cron_refresh_blocklist(self):
        """Frequency-based detection: any phone/email value attached to more
        than N distinct leads is an intermediary identity, not a customer
        one. Genuine duplicate groups run 2-5 members; intermediary
        identities run far higher. Also flags structurally invalid emails
        (scraped filenames, template boilerplate) regardless of frequency,
        since those can hide below the threshold (e.g. 'user@domain.com').
        """
        thresholds = self._get_thresholds()
        self.env.cr.execute("""
            SELECT value, field_type, lead_count FROM (
                SELECT phone_sanitized AS value, 'phone' AS field_type, count(DISTINCT id) AS lead_count
                FROM crm_lead WHERE phone_sanitized IS NOT NULL GROUP BY phone_sanitized
                UNION ALL
                SELECT x_mobile_phone AS value, 'phone' AS field_type, count(DISTINCT id) AS lead_count
                FROM crm_lead WHERE x_mobile_phone IS NOT NULL AND x_mobile_phone != '' GROUP BY x_mobile_phone
                UNION ALL
                SELECT email_normalized AS value, 'email' AS field_type, count(DISTINCT id) AS lead_count
                FROM crm_lead WHERE email_normalized IS NOT NULL GROUP BY email_normalized
            ) freq
            WHERE (field_type = 'phone' AND lead_count >= %(phone_th)s)
               OR (field_type = 'email' AND lead_count >= %(email_th)s)
        """, {'phone_th': thresholds['phone'], 'email_th': thresholds['email']})
        frequency_hits = self.env.cr.dictfetchall()

        self.env.cr.execute("""
            SELECT email_normalized AS value, 'email' AS field_type, count(DISTINCT id) AS lead_count
            FROM crm_lead
            WHERE email_normalized IS NOT NULL AND (
                email_normalized ~* '\\.(png|jpg|jpeg|gif|svg|webp)$'
                OR email_normalized ~* '^(user|test|admin|info|example|name|noreply)@(domain|example|test|company|yourcompany)\\.(com|co)$'
            )
            GROUP BY email_normalized
        """)
        literal_hits = self.env.cr.dictfetchall()

        now = fields.Datetime.now()
        all_records = self.search([])
        existing = {(b.value, b.field_type): b for b in all_records}
        seen = set()
        for row, source in [(r, 'frequency') for r in frequency_hits] + [(r, 'literal') for r in literal_hits]:
            key = (row['value'], row['field_type'])
            if key in seen:
                continue
            seen.add(key)
            vals = {
                'value': row['value'],
                'field_type': row['field_type'],
                'lead_count': row['lead_count'],
                'source': source,
                'last_refreshed': now,
                'active': True,
            }
            rec = existing.get(key)
            if rec:
                rec.write({'lead_count': row['lead_count'], 'last_refreshed': now})
            else:
                self.create(vals)

        stale = all_records.filtered(lambda b: (b.value, b.field_type) not in seen and b.source != 'manual')
        stale.write({'active': False})
