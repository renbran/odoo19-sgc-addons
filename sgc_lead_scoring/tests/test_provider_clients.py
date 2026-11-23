# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase


class TestProviderClients(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['web.research.provider'].search([]).unlink()
        # These tests exercise Tavily/Exa/Google directly; opt in past the
        # master kill switch (Task 1) so get_available_chain() doesn't
        # silently restrict the chain to searxng-only.
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'True')
        self.service = self.env['web.research.service']

    def _mock_response(self, status_code, json_data, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.headers = headers or {}
        return resp

    @patch('requests.post')
    def test_tavily_200_returns_results(self, mock_post):
        provider = self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'k', 'active': True,
        })
        mock_post.return_value = self._mock_response(200, {
            'results': [{'title': 'Acme', 'url': 'https://acme.com', 'content': 'snippet'}]
        })
        result = self.service.search('acme corp', providers=['tavily'])
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Acme')
        self.assertEqual(provider.total_requests, 1)
        self.assertEqual(provider.failed_requests, 0)

    @patch('requests.post')
    def test_tavily_429_marks_failure_no_crash(self, mock_post):
        provider = self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'k', 'active': True,
        })
        mock_post.return_value = self._mock_response(429, {}, headers={'Retry-After': '30'})
        result = self.service.search('acme corp', providers=['tavily'])
        self.assertFalse(result['success'])
        self.assertEqual(provider.failed_requests, 1)

    @patch('requests.post')
    def test_tavily_500_marks_failure(self, mock_post):
        provider = self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'k', 'active': True,
        })
        mock_post.return_value = self._mock_response(500, {})
        result = self.service.search('acme corp', providers=['tavily'])
        self.assertFalse(result['success'])
        self.assertEqual(provider.failed_requests, 1)

    @patch('requests.post')
    def test_exa_200_returns_results(self, mock_post):
        self.env['web.research.provider'].create({
            'name': 'Exa', 'provider_type': 'exa', 'api_key': 'k', 'active': True,
        })
        mock_post.return_value = self._mock_response(200, {
            'results': [{'title': 'Beta Inc', 'url': 'https://beta.com', 'text': 'snippet'}]
        })
        result = self.service.search('beta inc', providers=['exa'])
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Beta Inc')

    @patch('requests.post')
    def test_serper_200_returns_results(self, mock_post):
        self.env['web.research.provider'].create({
            'name': 'Serper', 'provider_type': 'serper', 'api_key': 'k', 'active': True,
        })
        mock_post.return_value = self._mock_response(200, {
            'organic': [{'title': 'Zeta Corp', 'link': 'https://zeta.com', 'snippet': 'snippet'}]
        })
        result = self.service.search('zeta corp', providers=['serper'])
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Zeta Corp')

    @patch('requests.post')
    def test_serper_401_marks_failure(self, mock_post):
        provider = self.env['web.research.provider'].create({
            'name': 'Serper', 'provider_type': 'serper', 'api_key': 'bad', 'active': True,
        })
        mock_post.return_value = self._mock_response(401, {})
        result = self.service.search('zeta corp', providers=['serper'])
        self.assertFalse(result['success'])
        self.assertFalse(provider.active)

    @patch('requests.get')
    def test_serpapi_200_returns_results(self, mock_get):
        self.env['web.research.provider'].create({
            'name': 'SerpAPI', 'provider_type': 'serpapi', 'api_key': 'k', 'active': True,
        })
        mock_get.return_value = self._mock_response(200, {
            'organic_results': [{'title': 'Eta LLC', 'link': 'https://eta.com', 'snippet': 'snippet'}]
        })
        result = self.service.search('eta llc', providers=['serpapi'])
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Eta LLC')

    @patch('requests.get')
    def test_serpapi_429_marks_failure(self, mock_get):
        provider = self.env['web.research.provider'].create({
            'name': 'SerpAPI', 'provider_type': 'serpapi', 'api_key': 'k',
            'daily_quota_limit': 100, 'active': True,
        })
        mock_get.return_value = self._mock_response(429, {}, headers={'Retry-After': '30'})
        result = self.service.search('eta llc', providers=['serpapi'])
        self.assertFalse(result['success'])
        self.assertGreaterEqual(provider.daily_quota_used, provider.daily_quota_limit)

    @patch('os.environ.get')
    @patch('requests.post')
    def test_env_var_api_key_overrides_db_field(self, mock_post, mock_env_get):
        """Live-deployment credential source: TAVILY_API_KEY env var takes
        priority over the provider.api_key DB field so real keys never have
        to be written into the database."""
        mock_env_get.side_effect = lambda name, default=None: (
            'env-secret-key' if name == 'TAVILY_API_KEY' else default
        )
        self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'db-placeholder-key', 'active': True,
        })
        mock_post.return_value = self._mock_response(200, {
            'results': [{'title': 'Acme', 'url': 'https://acme.com', 'content': 'snippet'}]
        })
        self.service.search('acme corp', providers=['tavily'])
        sent_key = mock_post.call_args.kwargs['json']['api_key']
        self.assertEqual(sent_key, 'env-secret-key')

    @patch('requests.get')
    def test_searxng_200_returns_results(self, mock_get):
        self.env['web.research.provider'].create({
            'name': 'SearXNG', 'provider_type': 'searxng',
            'base_url': 'https://searxng.example.com/search', 'active': True,
        })
        mock_get.return_value = self._mock_response(200, {
            'results': [{'title': 'Gamma LLC', 'url': 'https://gamma.com', 'content': 'snippet'}]
        })
        result = self.service.search('gamma llc', providers=['searxng'])
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Gamma LLC')

    @patch('requests.get')
    def test_google_401_marks_failure(self, mock_get):
        self.env['web.research.provider'].create({
            'name': 'Google', 'provider_type': 'google', 'api_key': 'bad-key',
            'search_engine_id': 'eid', 'active': True,
        })
        mock_get.return_value = self._mock_response(401, {})
        result = self.service.search('delta corp', providers=['google'])
        self.assertFalse(result['success'])

    @patch('requests.get')
    def test_search_google_custom_compat_shim(self, mock_get):
        self.env['web.research.provider'].create({
            'name': 'Google', 'provider_type': 'google', 'api_key': 'k',
            'search_engine_id': 'eid', 'active': True,
        })
        mock_get.return_value = self._mock_response(200, {
            'items': [{'title': 'Epsilon', 'link': 'https://epsilon.com', 'snippet': 'snippet'}]
        })
        result = self.service.search_google_custom('epsilon corp', num_results=3)
        self.assertTrue(result['success'])
        self.assertEqual(result['results'][0]['title'], 'Epsilon')


class TestProviderErrorHandling(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['web.research.provider'].search([]).unlink()
        self.env['ir.config_parameter'].sudo().set_param('llm_lead_scoring.allow_third_party_search', 'True')
        self.service = self.env['web.research.service']

    def _mock_response(self, status_code, json_data, headers=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data
        resp.headers = headers or {}
        return resp

    @patch('requests.post')
    def test_429_marks_provider_at_quota_for_today(self, mock_post):
        provider = self.env['web.research.provider'].create({
            'name': 'Tavily', 'provider_type': 'tavily', 'api_key': 'k',
            'daily_quota_limit': 1000, 'active': True,
        })
        mock_post.return_value = self._mock_response(429, {}, headers={'Retry-After': '30'})
        self.service.search('acme corp', providers=['tavily'])
        self.assertGreaterEqual(provider.daily_quota_used, provider.daily_quota_limit)
        self.assertFalse(provider.is_available())

    @patch('requests.get')
    def test_401_deactivates_provider_and_notifies_admin(self, mock_get):
        provider = self.env['web.research.provider'].create({
            'name': 'Google', 'provider_type': 'google', 'api_key': 'bad',
            'search_engine_id': 'eid', 'active': True,
        })
        mock_get.return_value = self._mock_response(401, {})
        self.service.search('acme corp', providers=['google'])
        self.assertFalse(provider.active)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'web.research.provider'), ('res_id', '=', provider.id),
        ])
        self.assertTrue(activities)
