# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api

_AUDIT_RETENTION_DAYS = 90


class WebResearchAudit(models.Model):
    _name = 'web.research.audit'
    _description = 'Web Research Audit Log'
    _order = 'create_date desc'

    provider_id = fields.Many2one('web.research.provider', required=True, ondelete='cascade')
    query_hash = fields.Char(required=True, index=True)
    lead_id = fields.Many2one('crm.lead', ondelete='set null')
    success = fields.Boolean()
    latency_ms = fields.Integer()
    result_count = fields.Integer()

    @api.model
    def log_call(self, provider, query_hash, lead, success, latency_ms, result_count):
        return self.create({
            'provider_id': provider.id,
            'query_hash': query_hash,
            'lead_id': lead.id if lead else False,
            'success': success,
            'latency_ms': latency_ms,
            'result_count': result_count,
        })

    @api.model
    def _cron_purge_old(self):
        cutoff = fields.Datetime.now() - timedelta(days=_AUDIT_RETENTION_DAYS)
        self.search([('create_date', '<', cutoff)]).unlink()
        return True
