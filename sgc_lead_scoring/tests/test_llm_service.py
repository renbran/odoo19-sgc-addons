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
    def test_call_llm_minimax_success(self, mock_post):
        """MiniMax uses the generic OpenAI-shaped payload/parse branch."""
        minimax_provider = self.LLMProvider.create({
            'name': 'Test MiniMax',
            'provider_type': 'minimax',
            'api_key': 'test-api-key',
            'model_name': 'MiniMax-M2.7',
        })
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'base_resp': {'status_code': 0, 'status_msg': 'success'},
            'choices': [{'message': {'content': 'MiniMax response'}}],
        }
        mock_post.return_value = mock_response

        messages = [{'role': 'user', 'content': 'Test message'}]
        result = self.LLMService.call_llm(messages, provider=minimax_provider)

        self.assertTrue(result['success'])
        self.assertEqual(result['content'], 'MiniMax response')
        called_url = mock_post.call_args.args[0]
        self.assertEqual(called_url, 'https://api.minimax.io/v1/chat/completions')

    @patch('requests.post')
    def test_call_llm_minimax_base_resp_error_treated_as_failure(self, mock_post):
        """HTTP 200 with a non-zero base_resp.status_code is still a failure."""
        minimax_provider = self.LLMProvider.create({
            'name': 'Test MiniMax',
            'provider_type': 'minimax',
            'api_key': 'test-api-key',
            'model_name': 'MiniMax-M2.7',
        })
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'base_resp': {'status_code': 1008, 'status_msg': 'insufficient balance'},
        }
        mock_post.return_value = mock_response

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'hi'}], provider=minimax_provider)

        self.assertFalse(result['success'])
        self.assertIn('insufficient balance', result['error'])
        self.assertEqual(minimax_provider.failed_requests, 1)

    def test_call_llm_skips_when_circuit_open(self):
        provider = self.LLMProvider.create({
            'name': 'Test Provider', 'provider_type': 'openai',
            'api_key': 'test-key', 'model_name': 'gpt-4',
        })
        for _ in range(5):
            provider._cb_record_failure()
        self.assertFalse(provider.is_available())

        with patch('requests.post') as mock_post:
            result = self.LLMService.call_llm(
                [{'role': 'user', 'content': 'hi'}], provider=provider)
            mock_post.assert_not_called()
        self.assertFalse(result['success'])
        self.assertIn('circuit breaker', result['error'])

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

    # ------------------------------------------------------------------
    # Structured output (response_schema) — Decision C
    # ------------------------------------------------------------------

    def _make_provider(self, provider_type, model_name='test-model'):
        return self.LLMProvider.create({
            'name': 'Test %s' % provider_type,
            'provider_type': provider_type,
            'api_key': 'test-api-key',
            'model_name': model_name,
            'temperature': 0.0,
            'max_tokens': 100,
            'timeout': 30,
            'is_default': False,
        })

    def _mock_ok(self, mock_post):
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {
            'choices': [{'message': {'content': 'ok'}}]
        }
        mock_post.return_value = resp

    @patch('requests.post')
    def test_call_llm_response_schema_openai(self, mock_post):
        """OpenAI provider gets response_format with json_schema payload."""
        self._mock_ok(mock_post)
        openai_provider = self._make_provider('openai')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=openai_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        # The POST must have been called with json= including response_format
        self.assertEqual(mock_post.call_count, 1)
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        self.assertIsNotNone(sent_json)
        self.assertIn('response_format', sent_json)
        self.assertEqual(sent_json['response_format']['type'], 'json_schema')
        self.assertEqual(sent_json['response_format']['json_schema'], schema)

    @patch('requests.post')
    def test_call_llm_response_schema_groq(self, mock_post):
        """Groq provider gets response_format with json_schema payload."""
        self._mock_ok(mock_post)
        groq_provider = self._make_provider('groq')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=groq_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        self.assertIn('response_format', sent_json)
        self.assertEqual(sent_json['response_format']['json_schema'], schema)

    @patch('requests.post')
    def test_call_llm_response_schema_mistral(self, mock_post):
        """Mistral provider gets response_format with json_schema payload."""
        self._mock_ok(mock_post)
        mistral_provider = self._make_provider('mistral')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=mistral_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        self.assertIn('response_format', sent_json)
        self.assertEqual(sent_json['response_format']['type'], 'json_schema')
        self.assertEqual(sent_json['response_format']['json_schema'], schema)

    @patch('requests.post')
    def test_call_llm_response_schema_google(self, mock_post):
        """Google provider gets response_format with json_schema payload
        (structurally distinct branch: contents/generationConfig, not messages)."""
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]
        }
        mock_post.return_value = resp
        google_provider = self._make_provider('google')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=google_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        self.assertIsNotNone(sent_json)
        # Google payload uses 'contents'/'generationConfig', not 'messages'
        self.assertIn('contents', sent_json)
        self.assertIn('response_format', sent_json)
        self.assertEqual(sent_json['response_format']['type'], 'json_schema')
        self.assertEqual(sent_json['response_format']['json_schema'], schema)

    @patch('requests.post')
    def test_call_llm_response_schema_anthropic(self, mock_post):
        """Anthropic provider gets tool-use payload with JSON-only argument."""
        # Anthropic returns a different response shape (no 'choices')
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {
            'content': [{'type': 'text', 'text': 'ok'}]
        }
        mock_post.return_value = resp
        anthropic_provider = self._make_provider('anthropic')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=anthropic_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        # Anthropic path uses tool_use with a JSON-only argument
        self.assertIn('tools', sent_json)
        tools = sent_json['tools']
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]['name'], 'json_output')
        # Input schema should match what we passed
        self.assertEqual(tools[0]['input_schema'], schema)
        # tool_choice must force the model to use the json_output tool,
        # otherwise Anthropic defaults to tool_choice "auto" and may
        # respond in free text instead of constrained JSON.
        self.assertEqual(sent_json['tool_choice'], {'type': 'tool', 'name': 'json_output'})

    @patch('requests.post')
    def test_call_llm_response_schema_huggingface_no_op(self, mock_post):
        """HuggingFace provider ignores response_schema — caller uses prompt fallback."""
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = [{'generated_text': 'ok'}]
        mock_post.return_value = resp
        hf_provider = self._make_provider('huggingface')
        schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}

        result = self.LLMService.call_llm(
            [{'role': 'user', 'content': 'q'}],
            provider=hf_provider,
            response_schema=schema,
        )

        self.assertTrue(result['success'])
        sent_json = mock_post.call_args.kwargs.get('json') or mock_post.call_args[1].get('json')
        # No response_format / tools in the huggingface payload
        self.assertNotIn('response_format', sent_json)
        self.assertNotIn('tools', sent_json)
