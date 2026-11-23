# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo.fields import Datetime
from odoo.tests.common import TransactionCase


class TestWebResearchResultModel(TransactionCase):

    def test_store_and_get_cached_hit(self):
        Result = self.env['web.research.result']
        Result.store('hash123', 'acme corp profile', [{'title': 'Acme', 'url': 'https://acme.com'}], 'tavily')
        cached = Result.get_cached('hash123')
        self.assertTrue(cached)
        self.assertEqual(json.loads(cached.results_json)[0]['title'], 'Acme')

    def test_get_cached_miss_when_absent(self):
        Result = self.env['web.research.result']
        self.assertFalse(Result.get_cached('does-not-exist'))

    def test_get_cached_miss_when_expired(self):
        Result = self.env['web.research.result']
        Result.store('hash456', 'q', [], 'exa')
        row = Result.search([('query_hash', '=', 'hash456')])
        row.expires_at = Datetime.now() - timedelta(days=1)
        self.assertFalse(Result.get_cached('hash456'))

    def test_cron_purge_expired_removes_only_expired(self):
        Result = self.env['web.research.result']
        Result.store('fresh', 'q', [], 'tavily')
        Result.store('stale', 'q', [], 'tavily')
        stale_row = Result.search([('query_hash', '=', 'stale')])
        stale_row.expires_at = Datetime.now() - timedelta(days=1)
        Result._cron_purge_expired()
        self.assertTrue(Result.search([('query_hash', '=', 'fresh')]))
        self.assertFalse(Result.search([('query_hash', '=', 'stale')]))
