# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from unittest.mock import patch, Mock


class TestLLMService(TransactionCase):
    """Test LLM Service integration logic"""

    def setUp(self):
        super(TestLLMService, self).setUp()
        self.LLMService = self.env['llm.service']
        self.LLMProvider = self.env['llm.provider']

        # Create test provider
        self.provider = self.LLMProvider.create({
            'name': 'Test Provider',
            'provider_type': 'openai',
            'api_key': 'test-api-key',
            'model_name': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 2000,
            'timeout': 30,
            'is_default': True,
        })

    def test_get_scoring_weights_cached(self):
        """Test that scoring weights are cached"""
        # First call
        weights1 = self.LLMService._get_scoring_weights()
        self.assertIsInstance(weights1, dict)
        self.assertIn('completeness', weights1)
        self.assertIn('clarity', weights1)
        self.assertIn('engagement', weights1)

        # Second call should use cache
        weights2 = self.LLMService._get_scoring_weights()
        self.assertEqual(weights1, weights2)

    def test_get_config_bool_cached(self):
        """Test that boolean config parameters are cached"""
        # Test with default
        result1 = self.LLMService._get_config_bool('test.param', 'False')
        self.assertFalse(result1)

        result2 = self.LLMService._get_config_bool('test.param2', 'True')
        self.assertTrue(result2)

    @patch('requests.post')
    def test_call_llm_success(self, mock_post):
        """Test successful LLM API call"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Test message'}]
        result = self.LLMService.call_llm(messages, provider=self.provider)

        self.assertTrue(result['success'])
        self.assertEqual(result['content'], 'Test response')
        self.assertEqual(result['error'], '')
        self.assertEqual(result['retries'], 0)

    @patch('requests.post')
    def test_call_llm_retry_on_rate_limit(self, mock_post):
        """Test retry logic on rate limit (429)"""
        # First call returns 429, second succeeds
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.text = 'Rate limit exceeded'

        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            'choices': [{'message': {'content': 'Success after retry'}}]
        }

        mock_post.side_effect = [mock_response_429, mock_response_200]

        messages = [{'role': 'user', 'content': 'Test'}]
        result = self.LLMService.call_llm(messages, provider=self.provider, max_retries=3)

        self.assertTrue(result['success'])
        self.assertEqual(result['content'], 'Success after retry')
        self.assertEqual(result['retries'], 1)
        self.assertEqual(mock_post.call_count, 2)

    @patch('requests.post')
    def test_call_llm_max_retries_exceeded(self, mock_post):
        """Test that max retries works correctly"""
        # All calls return 429
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = 'Rate limit'
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Test'}]
        result = self.LLMService.call_llm(messages, provider=self.provider, max_retries=2)

        self.assertFalse(result['success'])
        self.assertIn('after 2 retries', result['error'])
        self.assertEqual(result['retries'], 2)

    @patch('requests.post')
    def test_call_llm_no_retry_on_client_error(self, mock_post):
        """Test that 4xx errors don't retry"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad request'
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Test'}]
        result = self.LLMService.call_llm(messages, provider=self.provider, max_retries=3)

        self.assertFalse(result['success'])
        self.assertEqual(result['retries'], 0)  # No retries for 4xx
        self.assertEqual(mock_post.call_count, 1)

    def test_call_llm_no_provider(self):
        """Test error when no provider configured"""
        # Delete the test provider
        self.provider.unlink()

        messages = [{'role': 'user', 'content': 'Test'}]
        result = self.LLMService.call_llm(messages)

        self.assertFalse(result['success'])
        self.assertIn('No LLM provider configured', result['error'])
