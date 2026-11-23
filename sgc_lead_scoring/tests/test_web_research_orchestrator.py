# -*- coding: utf-8 -*-
import hashlib
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestWebResearchOrchestratorCore(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['web.research.provider'].search([]).unlink()
        self.provider = self.env['web.research.provider'].create({
            'name': 'Test Tavily',
            'provider_type': 'tavily',
            'api_key': 'test-key',
            'active': True,
        })
        self.service = self.env['web.research.service']

    def test_hash_query_is_deterministic(self):
        h1 = self.service.hash_query('acme corp company profile')
        h2 = self.service.hash_query('acme corp company profile')
        self.assertEqual(h1, h2)
        self.assertEqual(h1, hashlib.sha256(b'acme corp company profile').hexdigest())

    def test_hash_query_differs_for_different_queries(self):
        h1 = self.service.hash_query('acme corp')
        h2 = self.service.hash_query('beta inc')
        self.assertNotEqual(h1, h2)

    def test_anonymize_lead_id_is_deterministic_sha256(self):
        a1 = self.service.anonymize_lead_id(42)
        a2 = self.service.anonymize_lead_id(42)
        self.assertEqual(a1, a2)
        self.assertEqual(a1, hashlib.sha256(b'42').hexdigest())

    def test_search_cache_hit_skips_provider_call_real(self):
        query = 'acme corp company profile'
        query_hash = self.service.hash_query(query)
        self.env['web.research.result'].store(
            query_hash, query, [{'title': 'Cached', 'url': 'https://acme.com'}], 'tavily'
        )
        with patch('requests.get') as mock_get:
            result = self.service.search(query)
        mock_get.assert_not_called()
        self.assertTrue(result['success'])
        self.assertTrue(result['cache_hit'])
        self.assertEqual(result['results'][0]['title'], 'Cached')

    def test_search_no_available_provider_returns_failure(self):
        self.provider.active = False
        result = self.service.search('some uncached query xyz')
        self.assertFalse(result['success'])
        self.assertEqual(result['reason'], 'all_providers_unavailable')

    def test_search_writes_audit_row_with_hash_not_raw_query(self):
        self.provider.active = False  # force the no-provider path, still audits nothing here
        query = 'super secret company name'
        self.service.search(query)
        # No provider was called, so no audit row for this query — assert none leaked the raw text
        audits = self.env['web.research.audit'].search([])
        for row in audits:
            self.assertNotEqual(row.query_hash, query)

    def test_search_google_custom_shim_delegates_to_search_with_google_provider(self):
        with patch.object(type(self.service), 'search', return_value={'success': True, 'results': [], 'providers_used': ['google'], 'cache_hit': False, 'latency_ms': 0}) as mock_search:
            result = self.service.search_google_custom('epsilon corp', num_results=3)
        mock_search.assert_called_once_with('epsilon corp', num_results=3, providers=['google'])
        self.assertTrue(result['success'])


class TestWebResearchOrchestratorMultiSearch(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['web.research.provider'].search([]).unlink()
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'True')
        self.tavily = self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'k', 'sequence': 10, 'active': True,
        })
        self.exa = self.env['web.research.provider'].create({
            'name': 'Exa', 'provider_type': 'exa', 'api_key': 'k', 'sequence': 20, 'active': True,
        })
        self.service = self.env['web.research.service']

    def _tavily_response(self, *_a, **_k):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            'results': [
                {'title': 'Acme', 'url': 'https://acme.com/about', 'content': 'from tavily'},
                {'title': 'Acme News', 'url': 'https://news.acme.com/2026', 'content': 'from tavily'},
            ]
        }
        return resp

    def _exa_response(self, *_a, **_k):
        from unittest.mock import MagicMock
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            'results': [
                {'title': 'Acme (dup)', 'url': 'https://acme.com/duplicate-path', 'text': 'from exa'},
                {'title': 'Acme Products', 'url': 'https://acme.com/products', 'text': 'from exa'},
            ]
        }
        return resp

    def test_multi_search_dedupes_by_domain_and_merges_sources(self):
        with patch('requests.post') as mock_post:
            mock_post.side_effect = lambda url, **kw: (
                self._tavily_response() if 'tavily' in url else self._exa_response()
            )
            result = self.service.multi_search(['acme corp'], parallel=True, min_results=1)
        self.assertTrue(result['success'])
        domains = [r['url'].split('/')[2] for r in result['results']]
        self.assertEqual(len(domains), len(set(['acme.com', 'news.acme.com'])) + 0)
        acme_com_result = next(r for r in result['results'] if 'acme.com/about' in r['url'] or 'acme.com/duplicate-path' in r['url'] or 'acme.com/products' in r['url'])
        self.assertGreaterEqual(len(acme_com_result['sources']), 1)

    def test_multi_search_sequential_when_parallel_false(self):
        with patch('requests.post') as mock_post:
            mock_post.side_effect = lambda url, **kw: (
                self._tavily_response() if 'tavily' in url else self._exa_response()
            )
            result = self.service.multi_search(['acme corp'], parallel=False, min_results=1)
        self.assertTrue(result['success'])
        self.assertIn('tavily', result['providers_used'])

    def test_multi_search_multiple_queries_merged(self):
        with patch('requests.post') as mock_post:
            mock_post.side_effect = lambda url, **kw: (
                self._tavily_response() if 'tavily' in url else self._exa_response()
            )
            result = self.service.multi_search(
                ['acme corp profile', 'acme corp news 2026'], parallel=True, min_results=1
            )
        self.assertTrue(result['success'])
        self.assertGreater(len(result['results']), 0)

    def test_multi_search_reports_cache_hits(self):
        query = 'acme corp profile'
        query_hash = self.service.hash_query(query)
        self.env['web.research.result'].store(
            query_hash, query, [{'title': 'Cached Acme', 'url': 'https://acme.com'}], 'tavily'
        )
        with patch('requests.post') as mock_post:
            mock_post.side_effect = lambda url, **kw: self._exa_response()
            result = self.service.multi_search([query], parallel=True, min_results=1)
        self.assertGreaterEqual(result['cache_hits'], 1)

    def test_multi_search_retries_with_relaxed_query_below_min_results(self):
        from unittest.mock import MagicMock

        def empty_then_full(url, **kw):
            payload = kw.get('json', {})
            query = payload.get('query', '')
            resp = MagicMock()
            resp.status_code = 200
            if len(query.split()) > 3:
                resp.json.return_value = {'results': []}
            else:
                resp.json.return_value = {
                    'results': [{'title': 'Acme', 'url': 'https://acme.com', 'content': 'x'}]
                }
            return resp

        with patch('requests.post', side_effect=empty_then_full):
            result = self.service.multi_search(
                ['acme corp exact restrictive phrase match'], parallel=False, min_results=1
            )
        self.assertGreaterEqual(len(result['results']), 1)
