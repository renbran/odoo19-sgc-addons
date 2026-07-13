import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    """Extends mail.message to support OpenAI-compatible message formatting."""

    _inherit = "mail.message"

    def openai_format_message(self, model=None, **kwargs):
        """Format a mail.message record for OpenAI/Groq API consumption.

        Returns a dict with role and content suitable for the OpenAI
        chat completions endpoint.

        Args:
            model: Optional model name for formatting hints.

        Returns:
            dict with 'role' and 'content' keys.
        """
        self.ensure_one()

        role = self._get_openai_role()
        content = self._get_openai_content()

        message = self._build_openai_message(role, content)

        # Add tool call info if present
        if self._is_tool_call():
            message["tool_calls"] = self._get_tool_calls()
        if self._is_tool_response():
            message["tool_call_id"] = self._get_tool_call_id()

        return message

    def _get_openai_role(self):
        """Determine the OpenAI role for this message.

        Returns:
            str: One of 'system', 'user', 'assistant', 'tool'.
        """
        # Map message subtypes to OpenAI roles
        role_map = {
            "comment": "user",
            "email": "user",
            "notification": "assistant",
        }
        role = role_map.get(self.message_type, "user")

        # Check if from AI (subtype or author)
        if self.author_id and self.author_id.llm_provider:
            role = "assistant"
        elif self.subtype_id and self.subtype_id.xml_id == "mail.mt_comment":
            # Check message context for AI origin
            if self._context.get("llm_message"):
                role = "assistant"

        return role

    def _get_openai_content(self):
        """Extract and format message content for OpenAI.

        Returns:
            str: The message body content.
        """
        body = self.body or ""

        # Add attachment context if present
        if self.attachment_ids:
            attachment_info = []
            for att in self.attachment_ids:
                att_info = att.name or att.display_name or att.id
                att_type = att.mimetype or "unknown"
                attachment_info.append(f"[{att_type}] {att_info}")

            if attachment_info:
                body += "\n\n" + _("Attachments: %s") % ", ".join(attachment_info)

        return body

    def _build_openai_message(self, role, content):
        """Build the OpenAI message dict.

        Args:
            role: Message role.
            content: Message content.

        Returns:
            dict with role and content.
        """
        return {
            "role": role,
            "content": content,
        }

    def _is_tool_call(self):
        """Check if this message contains tool calls.

        Returns:
            bool: True if message has tool calls.
        """
        return bool(self._context.get("llm_tool_calls"))

    def _get_tool_calls(self):
        """Get tool calls from message context.

        Returns:
            list of tool call dicts or empty list.
        """
        return self._context.get("llm_tool_calls", [])

    def _is_tool_response(self):
        """Check if this message is a response to a tool call.

        Returns:
            bool: True if message is a tool response.
        """
        return bool(self._context.get("llm_tool_call_id"))

    def _get_tool_call_id(self):
        """Get the tool call ID this message responds to.

        Returns:
            str: Tool call ID or empty string.
        """
        return self._context.get("llm_tool_call_id", "")

    def openai_format_messages(self, model=None, **kwargs):
        """Format multiple messages for OpenAI API.

        Args:
            model: Optional model name.

        Returns:
            list of formatted message dicts.
        """
        return [msg.openai_format_message(model=model, **kwargs) for msg in self]

    def _get_thread_messages_openai(self, thread, limit=50):
        """Get formatted messages from a thread.

        Args:
            thread: mail.message record (parent message or thread root).
            limit: Max messages to return.

        Returns:
            list of formatted message dicts.
        """
        domain = [
            ("model", "=", thread.model),
            ("res_id", "=", thread.res_id),
        ]
        messages = self.search(domain, limit=limit, order="date ASC")
        return messages.openai_format_messages()

    @api.model
    def _prepare_openai_chat_context(self, thread, system_prompt=None, model=None):
        """Prepare full chat context including system prompt and thread messages.

        Args:
            thread: Thread root message.
            system_prompt: Optional system prompt text.
            model: Optional model name.

        Returns:
            list of message dicts ready for API call.
        """
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        thread_messages = self._get_thread_messages_openai(thread)
        messages.extend(thread_messages)

        return messages
