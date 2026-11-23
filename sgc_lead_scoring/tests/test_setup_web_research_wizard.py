# -*- coding: utf-8 -*-
from unittest.mock import patch, MagicMock

from odoo.tests.common import TransactionCase


class TestSetupWebResearchWizard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['web.research.provider'].search([]).unlink()

    @patch('requests.post')
    def test_action_test_connection_success(self, mock_post):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {'results': [{'title': 'Acme', 'url': 'https://acme.com', 'content': 'x'}]}
        mock_post.return_value = resp
        wizard = self.env['setup.web.research.wizard'].create({
            'provider_type': 'tavily', 'api_key': 'test-key', 'test_query': 'Acme Corp',
        })
        wizard.action_test_connection()
        self.assertTrue(wizard.test_success)
        self.assertIn('Acme', wizard.test_result)

    @patch('requests.post')
    def test_action_test_connection_failure(self, mock_post):
        resp = MagicMock()
        resp.status_code = 401
        resp.json.return_value = {}
        mock_post.return_value = resp
        wizard = self.env['setup.web.research.wizard'].create({
            'provider_type': 'tavily', 'api_key': 'bad-key', 'test_query': 'Acme Corp',
        })
        wizard.action_test_connection()
        self.assertFalse(wizard.test_success)

    def test_action_save_provider_creates_active_record(self):
        wizard = self.env['setup.web.research.wizard'].create({
            'provider_type': 'exa', 'api_key': 'my-exa-key',
        })
        wizard.action_save_provider()
        provider = self.env['web.research.provider'].search([('provider_type', '=', 'exa')])
        self.assertTrue(provider)
        self.assertTrue(provider.active)
        self.assertEqual(provider.api_key, 'my-exa-key')

    def test_action_save_provider_updates_existing_record(self):
        self.env['web.research.provider'].create({
            'name': 'Exa', 'provider_type': 'exa', 'api_key': 'old-key', 'active': False,
        })
        wizard = self.env['setup.web.research.wizard'].create({
            'provider_type': 'exa', 'api_key': 'new-key',
        })
        wizard.action_save_provider()
        providers = self.env['web.research.provider'].search([('provider_type', '=', 'exa')])
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers.api_key, 'new-key')
        self.assertTrue(providers.active)
