import json
import logging

from odoo import _

_logger = logging.getLogger(__name__)


class OpenAIFormatException(Exception):
    """Exception raised for OpenAI format validation errors."""
    pass


class OpenAIThreadValidator:
    """Validates chat message threads for OpenAI API compliance.

    Ensures message structure, role ordering, and content format
    meet OpenAI API requirements.
    """

    VALID_ROLES = {"system", "user", "assistant", "tool"}

    @classmethod
    def validate_thread(cls, messages):
        """Validate a thread of messages for OpenAI API use.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            bool: True if valid.

        Raises:
            OpenAIFormatException: If validation fails with details.
        """
        if not isinstance(messages, list):
            raise OpenAIFormatException(
                _("Messages must be a list, got %s") % type(messages).__name__
            )

        if not messages:
            raise OpenAIFormatException(
                _("Message list is empty")
            )

        for i, msg in enumerate(messages):
            cls._validate_message(msg, i)
            # Check that tool messages reference a valid tool_call_id
            if msg.get("role") == "tool" and not msg.get("tool_call_id"):
                raise OpenAIFormatException(
                    _("Message %(index)d: tool role requires 'tool_call_id'", index=i)
                )

        cls._validate_ordering(messages)
        return True

    @classmethod
    def _validate_message(cls, msg, index):
        """Validate a single message."""
        if not isinstance(msg, dict):
            raise OpenAIFormatException(
                _("Message %(index)d must be a dict, got %(type)s",
                  index=index, type=type(msg).__name__)
            )

        if "role" not in msg:
            raise OpenAIFormatException(
                _("Message %(index)d is missing 'role' field", index=index)
            )

        if msg["role"] not in cls.VALID_ROLES:
            raise OpenAIFormatException(
                _("Message %(index)d: invalid role '%(role)s'. Valid roles: %(roles)s",
                  index=index, role=msg["role"], roles=", ".join(cls.VALID_ROLES))
            )

        # Validate content (can be None for tool calls)
        if "content" not in msg and msg.get("role") not in ("assistant",):
            raise OpenAIFormatException(
                _("Message %(index)d is missing 'content' field", index=index)
            )

        # Check for multi-part content
        if isinstance(msg.get("content"), list):
            cls._validate_multipart_content(msg["content"], index)

        # Check for tool calls
        if msg.get("tool_calls") is not None:
            cls._validate_tool_calls(msg["tool_calls"], index)

    @classmethod
    def _validate_multipart_content(cls, content, index):
        """Validate multi-part content array."""
        for part_idx, part in enumerate(content):
            if not isinstance(part, dict):
                raise OpenAIFormatException(
                    _("Message %(msg_idx)d: content part %(part_idx)d must be a dict",
                      msg_idx=index, part_idx=part_idx)
                )
            if "type" not in part:
                raise OpenAIFormatException(
                    _("Message %(msg_idx)d: content part %(part_idx)d missing 'type'",
                      msg_idx=index, part_idx=part_idx)
                )

    @classmethod
    def _validate_tool_calls(cls, tool_calls, index):
        """Validate tool_calls in assistant messages."""
        if not isinstance(tool_calls, list):
            raise OpenAIFormatException(
                _("Message %(index)d: 'tool_calls' must be a list", index=index)
            )
        for tc_idx, tc in enumerate(tool_calls):
            if not isinstance(tc.get("function"), dict):
                raise OpenAIFormatException(
                    _("Message %(index)d: tool_call %(tc_idx)d missing 'function' object",
                      index=index, tc_idx=tc_idx)
                )
            if not tc.get("function", {}).get("name"):
                raise OpenAIFormatException(
                    _("Message %(index)d: tool_call %(tc_idx)d missing function 'name'",
                      index=index, tc_idx=tc_idx)
                )

    @classmethod
    def _validate_ordering(cls, messages):
        """Validate message ordering per OpenAI requirements."""
        for i in range(1, len(messages)):
            curr_role = messages[i]["role"]
            prev_role = messages[i - 1]["role"]

            # Tool message must follow assistant message with tool_calls
            if curr_role == "tool":
                if prev_role not in ("assistant", "tool"):
                    cls._log_warning(
                        _("Tool message at index %d should follow assistant or tool message",
                          i)
                    )

            # Assistant message with tool_calls should be followed by tool messages
            if prev_role == "assistant" and messages[i - 1].get("tool_calls"):
                if curr_role not in ("tool", "assistant"):
                    cls._log_warning(
                        _("Assistant message with tool_calls at index %(idx)d "
                          "should be followed by tool messages (got '%(role)s')",
                          idx=i - 1, role=curr_role)
                    )

    @staticmethod
    def _log_warning(msg):
        _logger.warning("OpenAI Thread Validation: %s", msg)

    @classmethod
    def sanitize_thread(cls, messages):
        """Clean and prepare thread for API submission.

        - Removes None content from non-assistant messages
        - Ensures all messages have required fields
        - Trims very long conversations

        Args:
            messages: List of message dicts.

        Returns:
            List of sanitized message dicts.
        """
        sanitized = []
        for msg in messages:
            clean = {k: v for k, v in msg.items() if k in (
                "role", "content", "tool_calls", "tool_call_id", "name"
            )}
            # Remove None content for non-assistant roles
            if clean.get("role") != "assistant" and clean.get("content") is None:
                clean.pop("content", None)
            sanitized.append(clean)
        return sanitized

    @classmethod
    def format_for_openai(cls, messages, model=None, system_prompt=None):
        """Format messages for direct OpenAI API call.

        Args:
            messages: List of message dicts (Odoo internal format)
            model: Optional model name for warnings
            system_prompt: Optional system prompt to prepend

        Returns:
            List of formatted messages ready for API call.
        """
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        for msg in messages:
            formatted.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        # Validate before returning
        cls.validate_thread(formatted)
        return formatted


class OpenAIResponseParser:
    """Parses OpenAI API responses into standardized Odoo format."""

    @staticmethod
    def parse_chat_response(response):
        """Extract content and metadata from chat completion response.

        Args:
            response: OpenAI ChatCompletion response object.

        Returns:
            dict with keys: content, tool_calls, model, usage, id
        """
        choice = response.choices[0]
        result = {
            "content": choice.message.content if choice.message.content else "",
            "model": response.model,
            "id": response.id,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
        }

        # Extract tool calls if present
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in choice.message.tool_calls
            ]

        return result

    @staticmethod
    def parse_embedding_response(response):
        """Extract embeddings from response."""
        return {
            "embeddings": [emb.embedding for emb in response.data],
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
        }

    @staticmethod
    def parse_stream_chunk(chunk):
        """Parse a single streaming chunk.

        Args:
            chunk: OpenAI streaming chunk object.

        Returns:
            dict with delta content, finish_reason, or None if done.
        """
        if not chunk.choices:
            return None

        delta = chunk.choices[0].delta
        result = {
            "content": delta.content if delta and delta.content else "",
            "finish_reason": chunk.choices[0].finish_reason,
        }

        # Handle tool calls in streaming
        if delta and hasattr(delta, "tool_calls") and delta.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name if tc.function else None,
                        "arguments": tc.function.arguments if tc.function else None,
                    }
                }
                for tc in delta.tool_calls
            ]

        return result

    @staticmethod
    def parse_models_response(response):
        """Parse models list response.

        Args:
            response: OpenAI Models response object.

        Returns:
            List of model dicts with id, created, owned_by.
        """
        return [
            {
                "id": model.id,
                "created": model.created,
                "owned_by": model.owned_by,
            }
            for model in response.data
        ]

    @staticmethod
    def format_error_response(error, model=None):
        """Create standardized error response.

        Args:
            error: Exception or error message.
            model: Optional model name for context.

        Returns:
            dict with error_code, error_message, content fields.
        """
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


class OpenAIMessageFormatter:
    """Handles formatting of Odoo messages to OpenAI format and back."""

    @staticmethod
    def odoo_message_to_openai(message):
        """Convert a single Odoo mail.message to OpenAI message format.

        Args:
            message: Odoo mail.message record.

        Returns:
            Dict with role and content for OpenAI API.
        """
        # Map Odoo message types to OpenAI roles
        role_map = {
            "comment": "user",
            "email": "user",
            "notification": "assistant",
            "user_notification": "assistant",
        }
        role = role_map.get(message.message_type, "user")

        # Build content
        body = message.body or ""
        content = body

        # If there are attachments, add them as context
        if message.attachment_ids:
            attachment_refs = message.attachment_ids.mapped("name")
            content += "\n\n[Attachments: " + ", ".join(attachment_refs) + "]"

        return {"role": role, "content": content}

    @staticmethod
    def openai_to_odoo_response(openai_response, model_name=None):
        """Convert OpenAI response to Odoo chat format.

        Args:
            openai_response: Parsed response dict from OpenAIResponseParser.
            model_name: Optional model name.

        Returns:
            Dict formatted for Odoo chat message creation.
        """
        result = {
            "body": openai_response.get("content", ""),
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        }

        if model_name:
            result["model_name"] = model_name

        # Add token usage tracking context
        usage = openai_response.get("usage", {})
        if usage:
            result["token_usage"] = usage

        return result

    @staticmethod
    def format_conversation_context(thread_messages, max_messages=20):
        """Format thread messages into OpenAI conversation context.

        Args:
            thread_messages: List of mail.message records.
            max_messages: Maximum number of messages to include.

        Returns:
            List of formatted message dicts.
        """
        context = []

        # Take the most recent messages
        recent = thread_messages[-max_messages:] if len(thread_messages) > max_messages else thread_messages

        for msg in recent:
            formatted = OpenAIMessageFormatter.odoo_message_to_openai(msg)
            context.append(formatted)

        return context


class OpenAIEmbeddingFormatter:
    """Handles formatting for embedding requests."""

    @staticmethod
    def format_input(input_data):
        """Format input for embedding API.

        Args:
            input_data: String or list of strings.

        Returns:
            Formatted input ready for API call.
        """
        if isinstance(input_data, str):
            return input_data
        elif isinstance(input_data, list):
            return [str(item) for item in input_data]
        else:
            return str(input_data)

    @staticmethod
    def parse_embedding_result(response_data):
        """Parse embedding API response into usable format.

        Args:
            response_data: Parsed response dict.

        Returns:
            List of embedding vectors.
        """
        return response_data.get("embeddings", [])
