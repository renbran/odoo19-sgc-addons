# -*- coding: utf-8 -*-
import json
from datetime import timedelta
from unittest.mock import patch

from odoo.fields import Datetime
from odoo.tests.common import TransactionCase


class TestWebResearchProviderModel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.provider = self.env['web.research.provider'].create({
            'name': 'Test Tavily',
            'provider_type': 'tavily',
            'api_key': 'test-key',
            'daily_quota_limit': 3,
        })

    def test_is_available_default(self):
        self.assertTrue(self.provider.is_available())

    def test_ssrf_guard_rejects_localhost(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['web.research.provider'].create({
                'name': 'Bad SearXNG',
                'provider_type': 'searxng',
                'base_url': 'http://localhost:8080/search',
            })

    def test_ssrf_guard_rejects_rfc1918(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['web.research.provider'].create({
                'name': 'Bad SearXNG 2',
                'provider_type': 'searxng',
                'base_url': 'http://192.168.1.5:8080/search',
            })

    def test_ssrf_guard_allows_public_host(self):
        provider = self.env['web.research.provider'].create({
            'name': 'Good SearXNG',
            'provider_type': 'searxng',
            'base_url': 'https://searxng.example.com/search',
        })
        self.assertTrue(provider.id)

    def test_quota_exhaustion_marks_unavailable(self):
        for _i in range(3):
            self.provider._quota_increment()
        self.assertFalse(self.provider.is_available())

    def test_quota_resets_next_day(self):
        for _i in range(3):
            self.provider._quota_increment()
        self.assertFalse(self.provider.is_available())
        self.provider.quota_reset_date = Datetime.now().date() - timedelta(days=1)
        self.assertTrue(self.provider.is_available())
        self.assertEqual(self.provider.daily_quota_used, 0)

    def test_circuit_opens_after_five_failures_in_window(self):
        for _i in range(5):
            self.provider._cb_record_failure()
        self.assertEqual(self.provider.circuit_state, 'open')
        self.assertFalse(self.provider.is_available())

    def test_circuit_stays_closed_under_five_failures(self):
        for _i in range(4):
            self.provider._cb_record_failure()
        self.assertEqual(self.provider.circuit_state, 'closed')
        self.assertTrue(self.provider.is_available())

    def test_circuit_half_open_after_open_until_elapsed(self):
        for _i in range(5):
            self.provider._cb_record_failure()
        self.assertEqual(self.provider.circuit_state, 'open')
        self.provider.circuit_open_until = Datetime.now() - timedelta(seconds=1)
        self.assertTrue(self.provider.is_available())
        self.assertEqual(self.provider.circuit_state, 'half_open')

    def test_circuit_half_open_success_closes(self):
        for _i in range(5):
            self.provider._cb_record_failure()
        self.provider.circuit_open_until = Datetime.now() - timedelta(seconds=1)
        self.provider.is_available()  # transitions to half_open
        self.provider._cb_record_success()
        self.assertEqual(self.provider.circuit_state, 'closed')
        self.assertEqual(json.loads(self.provider.failure_timestamps), [])

    def test_circuit_half_open_failure_doubles_backoff(self):
        for _i in range(5):
            self.provider._cb_record_failure()
        self.provider.circuit_open_until = Datetime.now() - timedelta(seconds=1)
        self.provider.is_available()  # transitions to half_open
        self.provider._cb_record_failure()
        self.assertEqual(self.provider.circuit_state, 'open')
        self.assertEqual(self.provider.circuit_backoff_seconds, 120)

    def test_get_available_chain_orders_by_sequence_and_excludes_open(self):
        Provider = self.env['web.research.provider']
        Provider.search([]).unlink()
        p1 = Provider.create({'name': 'A', 'provider_type': 'tavily', 'sequence': 20})
        p2 = Provider.create({'name': 'B', 'provider_type': 'exa', 'sequence': 10})
        for _i in range(5):
            p2._cb_record_failure()
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'True')
        chain = Provider.get_available_chain()
        self.assertEqual(chain.ids, [p1.id])

    def test_get_available_chain_kill_switch_restricts_to_searxng(self):
        Provider = self.env['web.research.provider']
        Provider.search([]).unlink()
        tavily = Provider.create({'name': 'Tavily', 'provider_type': 'tavily', 'sequence': 10})
        searxng = Provider.create({
            'name': 'SearXNG', 'provider_type': 'searxng', 'sequence': 20,
            'base_url': 'https://searxng.example.com/search',
        })
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'False')
        chain = Provider.get_available_chain()
        self.assertEqual(chain.ids, [searxng.id])
        self.assertNotIn(tavily.id, chain.ids)

    def test_get_available_chain_kill_switch_on_allows_third_party(self):
        Provider = self.env['web.research.provider']
        Provider.search([]).unlink()
        tavily = Provider.create({'name': 'Tavily', 'provider_type': 'tavily', 'sequence': 10})
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'True')
        chain = Provider.get_available_chain()
        self.assertEqual(chain.ids, [tavily.id])
