# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo.fields import Datetime
from odoo.tests.common import TransactionCase


class TestWebResearchAuditModel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.provider = self.env['web.research.provider'].create({
            'name': 'Test Tavily',
            'provider_type': 'tavily',
        })

    def test_log_call_creates_row(self):
        Audit = self.env['web.research.audit']
        row = Audit.log_call(self.provider, 'hash123', False, True, 350, 5)
        self.assertEqual(row.query_hash, 'hash123')
        self.assertTrue(row.success)
        self.assertEqual(row.latency_ms, 350)
        self.assertEqual(row.result_count, 5)

    def test_log_call_never_stores_raw_query(self):
        Audit = self.env['web.research.audit']
        row = Audit.log_call(self.provider, 'hash123', False, True, 100, 1)
        for field_name in row._fields:
            self.assertNotIn('acme corp confidential', str(row[field_name] or ''))

    def test_cron_purge_old_removes_rows_past_90_days(self):
        Audit = self.env['web.research.audit']
        old_row = Audit.log_call(self.provider, 'old-hash', False, True, 100, 1)
        old_row.create_date = Datetime.now() - timedelta(days=91)
        fresh_row = Audit.log_call(self.provider, 'fresh-hash', False, True, 100, 1)
        Audit._cron_purge_old()
        self.assertFalse(old_row.exists())
        self.assertTrue(fresh_row.exists())
