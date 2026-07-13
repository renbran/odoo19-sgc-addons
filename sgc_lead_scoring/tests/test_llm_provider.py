# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestLLMProvider(TransactionCase):
    """Test LLM Provider model and validation"""

    def setUp(self):
        super(TestLLMProvider, self).setUp()
        self.LLMProvider = self.env['llm.provider']

    def test_create_provider(self):
        """Test creating a valid LLM provider"""
        provider = self.LLMProvider.create({
            'name': 'Test OpenAI',
            'provider_type': 'openai',
            'api_key': 'test-api-key',
            'model_name': 'gpt-3.5-turbo',
            'temperature': 0.7,
            'max_tokens': 2000,
            'timeout': 30,
        })
        self.assertTrue(provider.id)
        self.assertEqual(provider.name, 'Test OpenAI')
        self.assertEqual(provider.provider_type, 'openai')

    def test_temperature_validation(self):
        """Test temperature must be between 0.0 and 2.0"""
        # Valid temperature
        provider = self.LLMProvider.create({
            'name': 'Test Valid Temp',
            'provider_type': 'openai',
            'api_key': 'test-key',
            'model_name': 'gpt-4',
            'temperature': 1.0,
        })
        self.assertEqual(provider.temperature, 1.0)

        # Invalid temperature - too high
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Temp',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'temperature': 3.0,  # Invalid
            })

        # Invalid temperature - negative
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Temp2',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'temperature': -0.5,  # Invalid
            })

    def test_max_tokens_validation(self):
        """Test max_tokens must be reasonable"""
        # Valid max_tokens
        provider = self.LLMProvider.create({
            'name': 'Test Valid Tokens',
            'provider_type': 'openai',
            'api_key': 'test-key',
            'model_name': 'gpt-4',
            'max_tokens': 5000,
        })
        self.assertEqual(provider.max_tokens, 5000)

        # Invalid - too low
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Tokens',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'max_tokens': 0,  # Invalid
            })

        # Invalid - too high
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Tokens2',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'max_tokens': 200000,  # Invalid
            })

    def test_timeout_validation(self):
        """Test timeout must be reasonable"""
        # Valid timeout
        provider = self.LLMProvider.create({
            'name': 'Test Valid Timeout',
            'provider_type': 'openai',
            'api_key': 'test-key',
            'model_name': 'gpt-4',
            'timeout': 60,
        })
        self.assertEqual(provider.timeout, 60)

        # Invalid - too low
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Timeout',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'timeout': 2,  # Invalid
            })

        # Invalid - too high
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Test Invalid Timeout2',
                'provider_type': 'openai',
                'api_key': 'test-key',
                'model_name': 'gpt-4',
                'timeout': 400,  # Invalid
            })

    def test_single_default_provider(self):
        """Test only one provider can be default per company"""
        # Create first default provider
        provider1 = self.LLMProvider.create({
            'name': 'Default Provider 1',
            'provider_type': 'openai',
            'api_key': 'test-key-1',
            'model_name': 'gpt-4',
            'is_default': True,
        })
        self.assertTrue(provider1.is_default)

        # Try to create second default provider - should fail
        with self.assertRaises(ValidationError):
            self.LLMProvider.create({
                'name': 'Default Provider 2',
                'provider_type': 'groq',
                'api_key': 'test-key-2',
                'model_name': 'llama-3.1',
                'is_default': True,
            })

    def test_get_default_provider(self):
        """Test getting default provider"""
        # No providers yet
        default = self.LLMProvider.get_default_provider()
        self.assertFalse(default)

        # Create non-default provider
        provider1 = self.LLMProvider.create({
            'name': 'Non-Default Provider',
            'provider_type': 'openai',
            'api_key': 'test-key-1',
            'model_name': 'gpt-4',
            'is_default': False,
        })

        # Create default provider
        provider2 = self.LLMProvider.create({
            'name': 'Default Provider',
            'provider_type': 'groq',
            'api_key': 'test-key-2',
            'model_name': 'llama-3.1',
            'is_default': True,
        })

        # Get default should return provider2
        default = self.LLMProvider.get_default_provider()
        self.assertEqual(default.id, provider2.id)

    def test_increment_usage(self):
        """Test usage tracking"""
        provider = self.LLMProvider.create({
            'name': 'Test Provider',
            'provider_type': 'openai',
            'api_key': 'test-key',
            'model_name': 'gpt-4',
        })

        initial_requests = provider.total_requests
        initial_failed = provider.failed_requests

        # Increment successful request
        provider.increment_usage(success=True)
        self.assertEqual(provider.total_requests, initial_requests + 1)
        self.assertEqual(provider.failed_requests, initial_failed)

        # Increment failed request
        provider.increment_usage(success=False)
        self.assertEqual(provider.total_requests, initial_requests + 2)
        self.assertEqual(provider.failed_requests, initial_failed + 1)
