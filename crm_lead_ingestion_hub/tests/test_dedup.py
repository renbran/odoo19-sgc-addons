from psycopg2 import errors as pg_errors

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDedup(TransactionCase):

    def setUp(self):
        super().setUp()
        self.config = self.env['crm.lead.source.config'].create({
            'name': 'universal config',
            'provider': 'universal',
            'app_secret': 's',
        })

    def test_22_duplicate_dedup_key_second_call_marked_duplicate(self):
        Log = self.env['crm.lead.ingestion.log']
        Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'dup-1',
            'raw_payload': '{}',
            'parsed_payload': '{}',
            'status': 'received',
        })
        with self.assertRaises(pg_errors.UniqueViolation):
            with self.env.cr.savepoint():
                Log.create({
                    'source_config_id': self.config.id,
                    'dedup_key': 'dup-1',
                    'raw_payload': '{}',
                    'parsed_payload': '{}',
                    'status': 'received',
                })
        count = Log.search_count([('source_config_id', '=', self.config.id), ('dedup_key', '=', 'dup-1')])
        self.assertEqual(count, 1)

    def test_23_concurrent_duplicate_insert_blocked_by_constraint(self):
        Log = self.env['crm.lead.ingestion.log']
        Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'race-1',
            'raw_payload': '{}',
            'parsed_payload': '{}',
            'status': 'received',
        })
        with self.assertRaises(pg_errors.UniqueViolation):
            with self.env.cr.savepoint():
                Log.create({
                    'source_config_id': self.config.id,
                    'dedup_key': 'race-1',
                    'raw_payload': '{}',
                    'parsed_payload': '{}',
                    'status': 'received',
                })

    def test_24_different_dedup_keys_both_created(self):
        Log = self.env['crm.lead.ingestion.log']
        Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'key-a',
            'raw_payload': '{}',
            'parsed_payload': '{}',
            'status': 'received',
        })
        Log.create({
            'source_config_id': self.config.id,
            'dedup_key': 'key-b',
            'raw_payload': '{}',
            'parsed_payload': '{}',
            'status': 'received',
        })
        count = Log.search_count([('source_config_id', '=', self.config.id)])
        self.assertEqual(count, 2)
