# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo import models, fields, api

_CACHE_TTL_DAYS = 7


class WebResearchResult(models.Model):
    _name = 'web.research.result'
    _description = 'Web Research Cached Result'
    _rec_name = 'query_hash'

    query_hash = fields.Char(required=True, index=True)
    query_text = fields.Text()
    results_json = fields.Text()
    providers_used = fields.Char()
    created_at = fields.Datetime(default=fields.Datetime.now)
    expires_at = fields.Datetime(required=True)

    @api.model
    def get_cached(self, query_hash):
        row = self.search([('query_hash', '=', query_hash)], limit=1, order='created_at desc')
        if not row or row.expires_at < fields.Datetime.now():
            return False
        return row

    @api.model
    def store(self, query_hash, query_text, results, providers_used):
        now = fields.Datetime.now()
        return self.create({
            'query_hash': query_hash,
            'query_text': query_text,
            'results_json': json.dumps(results),
            'providers_used': providers_used,
            'created_at': now,
            'expires_at': now + timedelta(days=_CACHE_TTL_DAYS),
        })

    @api.model
    def _cron_purge_expired(self):
        expired = self.search([('expires_at', '<', fields.Datetime.now())])
        expired.unlink()
        return True
