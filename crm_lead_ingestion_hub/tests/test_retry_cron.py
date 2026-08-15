import json
from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRetryCron(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['crm.lead.source.config'].create({
            'name': 'universal config',
            'provider': 'universal',
            'app_secret': 's',
            'max_retries': 3,
            'backoff_interval_minutes': 10,
        })
        self.Log = self.env['crm.lead.ingestion.log']

    def test_25_retry_succeeds_when_backoff_elapsed(self):
        log = self.Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'retry-1',
            'raw_payload': '{}',
            'parsed_payload': json.dumps({'foo': 'bar'}),
            'status': 'failed',
            'retry_count': 0,
            'last_attempt': fields.Datetime.now() - timedelta(minutes=20),
        })
        self.Log._cron_retry_failed()
        log.invalidate_recordset()
        self.assertEqual(log.status, 'success')

    def test_26_retry_skipped_when_backoff_not_elapsed(self):
        log = self.Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'retry-2',
            'raw_payload': '{}',
            'parsed_payload': json.dumps({'foo': 'bar'}),
            'status': 'failed',
            'retry_count': 0,
            'last_attempt': fields.Datetime.now(),
        })
        self.Log._cron_retry_failed()
        log.invalidate_recordset()
        self.assertEqual(log.status, 'failed')
        self.assertEqual(log.retry_count, 0)

    def test_27_retry_stops_after_max_retries(self):
        log = self.Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'retry-3',
            'raw_payload': '{}',
            'parsed_payload': json.dumps({'foo': 'bar'}),
            'status': 'failed',
            'retry_count': 3,
            'last_attempt': fields.Datetime.now() - timedelta(days=1),
        })
        self.Log._cron_retry_failed()
        log.invalidate_recordset()
        self.assertEqual(log.retry_count, 3)
        self.assertEqual(log.status, 'failed')
