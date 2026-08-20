import json
import logging
import time
from datetime import datetime, timedelta

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class LLMProviderGroq(models.Model):
    """Groq AI Provider - OpenAI-compatible API integration.

    Provides chat, embedding, and model listing capabilities through
    Groq's OpenAI-compatible API endpoint. This module also hosts
    shared ``openai_*`` methods that ``llm_mistral._dispatch()`` routes to,
    so Mistral-based features continue working after ``llm_openai``
    is uninstalled.
    """

    _inherit = "llm.provider"

    # -------------------------------------------------------------------------
    # Service registration
    # -------------------------------------------------------------------------

    @api.model
    def _get_available_services(self):
        """Register 'groq' as an available LLM provider service."""
        services = super()._get_available_services()
        services.append(("groq", "Groq"))
        return services

    @api.model
    def _get_service_help(self):
        help_text = super()._get_service_help()
        help_text.update({
            "groq": _(
                "Groq provides fast AI inference via an OpenAI-compatible API. "
                "Supports open-source models like Llama, Mixtral, and Gemma. "
                "Use environment variable GROQ_API_KEY for authentication."
            ),
        })
        return help_text

    @api.model
    def _get_model_use_services(self):
        services = super()._get_model_use_services()
        services.update({
            "groq": ["chat", "embedding"],
        })
        return services

    # -------------------------------------------------------------------------
    # Dispatch — allows ``llm_mistral`` to route Mistral calls to shared
    # ``openai_*`` methods defined in this module.
    # -------------------------------------------------------------------------

    def _dispatch(self, method, *args, record=None, **kwargs):
        """Route a method call to the correct service implementation.

        For ``'groq'`` this dispatches to the ``openai_{method}``
        implementation provided by this module.

        For other services (e.g. ``'mistral'``) we pass through to
        the parent dispatch chain — ``llm_mistral`` handles its own
        ``mistral → openai_*`` routing.
        """
        if self.service == "groq":
            service_method = f"openai_{method}"
            record = record if record else self
            record_name = record._name
            if not hasattr(record, service_method):
                raise NotImplementedError(
                    _(
                        "The method %(method)s is not supported on the "
                        "model %(model)s for the service %(service)s",
                        method=service_method,
                        model=record_name,
                        service=self.service,
                    )
                )
            return getattr(record, service_method)(*args, **kwargs)

        return super()._dispatch(method, *args, record=record, **kwargs)

    # -------------------------------------------------------------------------
    # Client
    # -------------------------------------------------------------------------

    def openai_get_client(self):
        """Return an OpenAI-compatible client for the Groq API.

        Uses Python's ``openai`` library configured with:
        - ``api_key`` from ``GROQ_API_KEY`` env variable
        - ``base_url`` from ``GROQ_API_BASE`` env (default: groq.com)
        - ``http_client`` for connection timeout handling
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise UserError(
                _("The Python 'openai' package is required. Run: pip install openai")
            )

        api_key = self._get_api_key()
        api_base = self._get_api_base()

        return OpenAI(api_key=api_key, base_url=api_base)

    def _get_api_key(self):
        """Get API key from the freellmapi gateway when configured,
        otherwise fall back to the Groq key."""
        import os
        if os.environ.get("FREELLM_API_URL"):
            return os.environ.get("FREELLM_API_KEY") or self.api_key or ""
        return os.environ.get("GROQ_API_KEY") or self.api_key or ""

    def _get_api_base(self):
        """Get API base URL.

        Resolution order:
        1. ``FREELLM_API_URL`` environment variable (local gateway)
        2. ``GROQ_API_BASE`` environment variable
        3. ``api_base`` field on the provider record
        4. Default per service (Groq → ``https://api.groq.com/openai/v1``)
        """
        import os

        env_base = os.environ.get("FREELLM_API_URL")
        if env_base:
            return env_base.rstrip("/")
        env_base = os.environ.get("GROQ_API_BASE")
        if env_base:
            return env_base
        if self.api_base:
            return self.api_base
        if self.service == "groq":
            return "https://api.groq.com/openai/v1"
        # For other services (mistral via openai_*), let the OpenAI SDK
        # use its own default (api.openai.com/v1) — the real endpoint is
        # configured through self.api_base if needed.
        return None

    # -------------------------------------------------------------------------
    # Chat
    # -------------------------------------------------------------------------

    def openai_chat(
        self,
        messages,
        model=None,
        temperature=0.7,
        max_tokens=None,
        top_p=0.9,
        stream=False,
        stop=None,
        **kwargs,
    ):
        """Send a chat completion request to the Groq API.

        Args:
            messages: List of message dicts with ``role`` and ``content``.
            model: Model identifier.
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens in the response.
            top_p: Nucleus sampling parameter.
            stream: Whether to stream the response.
            stop: Optional stop sequences.

        Returns:
            Parsed response dict or a streaming generator.
        """
        client = self.openai_get_client()

        params = {
            "model": model or self._get_chat_model(),
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
        }

        if max_tokens:
            params["max_tokens"] = max_tokens
        if stop:
            params["stop"] = stop
        if stream:
            params["stream"] = stream

        # Merge extra kwargs (e.g. frequency_penalty, presence_penalty, …)
        params.update(kwargs)

        try:
            if stream:
                return self._openai_stream_chat(client, params)
            response = client.chat.completions.create(**params)
            return self._parse_chat_response(response)
        except Exception as e:
            _logger.exception("Groq chat completion failed: %s", e)
            return self._format_error_response(e, model=model)

    def _openai_stream_chat(self, client, params):
        """Handle streaming chat completion."""
        response = client.chat.completions.create(**params)
        full_content = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                yield delta.content or ""
        return full_content

    def _parse_chat_response(self, response):
        """Parse OpenAI-compatible chat response."""
        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "model": response.model,
            "id": response.id,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]
        return result

    def _format_error_response(self, error, model=None):
        """Create a standard error response dict."""
        error_msg = str(error)
        error_code = getattr(error, "code", "UNKNOWN")
        if hasattr(error, "status_code"):
            error_code = error.status_code
        elif hasattr(error, "http_status"):
            error_code = error.http_status

        return {
            "content": "",
            "error_code": error_code,
            "error_message": error_msg,
            "error": True,
            "model": model,
        }

    # -------------------------------------------------------------------------
    # Embedding
    # -------------------------------------------------------------------------

    def openai_embedding(self, input_data, model=None, **kwargs):
        """Generate embeddings via Groq API.

        Args:
            input_data: String or list of strings to embed.
            model: Embedding model name.

        Returns:
            dict with ``embeddings``, ``model``, ``usage``.
        """
        client = self.openai_get_client()

        params = {
            "model": model or self._get_embedding_model(),
            "input": input_data,
        }
        params.update(kwargs)

        try:
            response = client.embeddings.create(**params)
            return {
                "embeddings": [emb.embedding for emb in response.data],
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            }
        except Exception as e:
            _logger.exception("Groq embedding failed: %s", e)
            return self._format_error_response(e, model=model)

    # -------------------------------------------------------------------------
    # Model listing
    # -------------------------------------------------------------------------

    def openai_models(self, **kwargs):
        """List available models from the Groq API.

        Returns:
            List of model dicts with ``id``, ``created``, ``owned_by``.
        """
        client = self.openai_get_client()
        try:
            response = client.models.list(**kwargs)
            return [
                {
                    "id": model.id,
                    "created": model.created,
                    "owned_by": model.owned_by,
                }
                for model in response.data
            ]
        except Exception as e:
            _logger.exception("Groq model listing failed: %s", e)
            return []

    # -------------------------------------------------------------------------
    # Model parsing helpers
    # -------------------------------------------------------------------------

    def _get_chat_model(self):
        """Return the default chat model for this provider."""
        return "llama-3.3-70b-versatile"

    def _get_embedding_model(self):
        """Return the default embedding model for this provider."""
        return "text-embedding-ada-002"

    def openai_format_message(self, message, **kwargs):
        """Format a mail.message record for API consumption.

        Delegates to ``mail.message.openai_format_message()``.
        """
        return message.openai_format_message(**kwargs)

    def openai_format_messages(self, messages, **kwargs):
        """Format multiple mail.message records."""
        return [
            self.openai_format_message(msg, **kwargs) for msg in messages
        ]

    def openai_format_tools(self, tools):
        """Normalize Odoo tool definitions into the OpenAI tool format.

        Returns the input unchanged — the default ``openai`` tool format
        is already compatible with Groq's API.
        """
        return tools or []

    def openai_normalize_prepend_messages(self, prepend_messages):
        """Normalize prepend messages for the OpenAI-compatible format.

        OpenAI/Groq accepts both string and list content formats, so no
        transformation is needed.
        """
        return prepend_messages or []

    def openai_generate(self, input_data, model=None, stream=False, **kwargs):
        """Generate content via the OpenAI-compatible chat completion API.

        This maps the ``generate`` call to ``openai_chat``, wrapping
        ``input_data`` in a user message when necessary.
        """
        from odoo.addons.llm_provider.models.base import LLM_PROVIDER_OPENAI

        messages = []
        if isinstance(input_data, str):
            messages.append({"role": "user", "content": input_data})
        elif isinstance(input_data, list):
            messages = input_data
        return self.openai_chat(
            messages=messages, model=model, stream=stream, **kwargs
        )

    def _openai_parse_model(self, model_data):
        """Parse a raw model dict into Odoo model usage types.

        Args:
            model_data: Dict with ``id``, ``created``, ``owned_by`` keys.

        Returns:
            List of usage type strings (e.g. ``["chat"]``, ``["embedding"]``).
        """
        model_id = model_data.get("id", "")
        usages = []

        # Groq model naming conventions
        model_lower = model_id.lower()

        if any(name in model_lower for name in ("embed",)):
            usages.append("embedding")
        elif any(name in model_lower for name in ("whisper", "audio")):
            usages.append("transcription")
        elif any(name in model_lower for name in ("vision", "llama")):
            usages.append("chat")
        else:
            usages.append("chat")

        return usages

    # -------------------------------------------------------------------------
    # Training / Fine-tuning stubs
    # -------------------------------------------------------------------------

    def openai_create_training_job(self, **kwargs):
        """Create a fine-tuning job (stub — Groq does not support this yet)."""
        _logger.info("Groq create_training_job called (not supported)")
        return {
            "error": True,
            "error_message": _("Groq does not support fine-tuning jobs at this time"),
        }

    def openai_list_training_jobs(self, **kwargs):
        """List fine-tuning jobs (stub)."""
        _logger.info("Groq list_training_jobs called (not supported)")
        return []

    def openai_cancel_training_job(self, job_id, **kwargs):
        """Cancel a fine-tuning job (stub)."""
        _logger.info("Groq cancel_training_job called (not supported)")
        return {
            "error": True,
            "error_message": _("Groq does not support fine-tuning jobs at this time"),
        }

    def openai_delete_training_job(self, job_id, **kwargs):
        """Delete a fine-tuning job (stub)."""
        _logger.info("Groq delete_training_job called (not supported)")
        return {
            "error": True,
            "error_message": _("Groq does not support fine-tuning jobs at this time"),
        }

    def openai_get_training_job(self, job_id, **kwargs):
        """Get a fine-tuning job (stub)."""
        _logger.info("Groq get_training_job called (not supported)")
        return {
            "error": True,
            "error_message": _("Groq does not support fine-tuning jobs at this time"),
        }

    # -------------------------------------------------------------------------
    # Token counting / cost estimation
    # -------------------------------------------------------------------------

    def openai_count_tokens(self, messages, model=None):
        """Estimate token count for a list of messages.

        Uses a simple heuristic (4 chars ≈ 1 token) or tiktoken if available.
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model or "gpt-3.5-turbo")
            text = " ".join(m.get("content", "") for m in messages)
            return len(encoding.encode(text))
        except Exception:
            total_chars = sum(len(m.get("content", "")) for m in messages)
            return total_chars // 4

    def openai_estimate_cost(self, tokens, model=None, token_type="total"):
        """Estimate API cost based on token count (stub for Groq)."""
        # Groq is currently free / low-cost; return 0
        return 0.0

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def openai_validate_api_key(self):
        """Validate the configured API key by listing models.

        Returns:
            bool: True if the key is valid, False otherwise.
        """
        try:
            models = self.openai_models()
            return len(models) > 0
        except Exception as e:
            _logger.warning("Groq API key validation failed: %s", e)
            return False

    def _get_default_api_base(self):
        """Return the default API base URL for Groq."""
        return "https://api.groq.com/openai/v1"



    def mistral_get_default_ocr_model(self):
        raise UserError(
            _(
                "Groq providers do not support Mistral OCR features. "
                "Use a Mistral provider for OCR model lookups."
            )
        )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @api.constrains("service", "api_key")
    def _check_groq_configuration(self):
        """Validate Groq provider configuration."""
        for record in self:
            if record.service != "groq":
                continue
            if not self._get_api_key():
                raise ValidationError(
                    _(
                        "Groq API key is required. Set GROQ_API_KEY "
                        "environment variable or provide api_key."
                    )
                )

    # -------------------------------------------------------------------------
    # Retrieval-Augmented Generation helpers
    # -------------------------------------------------------------------------

    def openai_rag_search(self, query, knowledge_base=None, top_k=5, **kwargs):
        """Perform a RAG search using Groq embeddings.

        Args:
            query: Search query string.
            knowledge_base: Optional knowledge base record.
            top_k: Number of results to return.

        Returns:
            List of context dicts.
        """
        # Generate embedding for the query
        embedding_result = self.openai_embedding(query)
        if embedding_result.get("error"):
            _logger.error("RAG search failed: %s", embedding_result.get("error_message"))
            return []

        query_vector = embedding_result["embeddings"][0]

        # Search in knowledge base
        if knowledge_base:
            documents = self._search_similar_documents(query_vector, knowledge_base, top_k)
        else:
            documents = []

        return documents

    def _search_similar_documents(self, query_vector, knowledge_base, top_k=5):
        """Search for similar documents using vector similarity.

        Args:
            query_vector: Embedding vector for the query.
            knowledge_base: Knowledge base record.
            top_k: Number of results to return.

        Returns:
            List of document dicts with content and similarity.
        """
        # This is a placeholder for vector search integration.
        # Implement with your preferred vector DB (PostgreSQL pgvector, etc.)
        _logger.info("Vector search requested but not yet implemented for Groq")
        return []

    # -------------------------------------------------------------------------
    # Context / conversation helpers
    # -------------------------------------------------------------------------

    def openai_prepare_context(self, thread, system_prompt=None, model=None):
        """Prepare full context for a chat completion from a thread.

        Args:
            thread: Thread root message.
            system_prompt: Optional system prompt.
            model: Optional model name.

        Returns:
            List of message dicts.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        thread_messages = self._get_thread_messages_openai(thread)
        messages.extend(thread_messages)
        return messages

    def _get_thread_messages_openai(self, thread, limit=50):
        """Get formatted messages from a thread."""
        domain = [
            ("model", "=", thread.model),
            ("res_id", "=", thread.res_id),
        ]
        messages = self.env["mail.message"].search(domain, limit=limit, order="date ASC")
        return [
            self.openai_format_message(msg) for msg in messages
        ]
