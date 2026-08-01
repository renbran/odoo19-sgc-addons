# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

from .utils import as_markup, html_to_text

_logger = logging.getLogger(__name__)


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    sgc_ai_thread_id = fields.Many2one(
        "llm.thread",
        string="AI Conversation Thread",
        copy=False,
        help="LLM thread that keeps this live-chat conversation's AI memory.",
    )

    def _message_post_after_hook(self, message, msg_vals):
        res = super()._message_post_after_hook(message, msg_vals)
        for channel in self:
            try:
                channel._sgc_maybe_ai_reply(message)
            except Exception:  # never break the visitor's chat on an AI error
                _logger.exception(
                    "SGC live-chat AI reply failed on channel %s", channel.id
                )
        return res

    # ------------------------------------------------------------------
    def _sgc_maybe_ai_reply(self, message):
        self.ensure_one()
        if self.channel_type != "livechat":
            return
        lc = self.livechat_channel_id.sudo()
        if not lc or not lc.sgc_ai_enabled or not lc.sgc_ai_assistant_id:
            return
        # Let a scripted chatbot (if any) finish its flow first.
        if self.chatbot_current_step_id:
            return
        if not message or message.message_type != "comment":
            return
        operator = self.livechat_operator_id
        # Skip the operator's / our own messages -> prevents infinite recursion.
        if operator and message.author_id and message.author_id.id == operator.id:
            return
        user_text = html_to_text(message.body)
        if not user_text:
            return

        assistant = lc.sgc_ai_assistant_id
        if not assistant.provider_id or not assistant.model_id:
            _logger.warning(
                "SGC AI assistant %s has no provider/model set; skipping reply.",
                assistant.name,
            )
            return

        thread = self._sgc_get_ai_thread(assistant)
        reply_html = thread.sgc_generate_reply(user_text)
        if not reply_html:
            return

        # Post the answer as the channel operator (the AI bot). Because the
        # author is the operator, the guard above stops it from re-triggering.
        self.message_post(
            body=as_markup(reply_html),
            author_id=operator.id if operator else False,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    # ------------------------------------------------------------------
    def _sgc_get_ai_thread(self, assistant):
        self.ensure_one()
        if self.sgc_ai_thread_id:
            return self.sgc_ai_thread_id.sudo()
        thread = self.env["llm.thread"].sudo().create(
            {
                "name": "Livechat AI - %s" % (self.name or self.id),
                "provider_id": assistant.provider_id.id,
                "model_id": assistant.model_id.id,
            }
        )
        # Applies provider/model/prompt/tools from the assistant.
        thread.set_assistant(assistant.id)
        self.sudo().sgc_ai_thread_id = thread.id
        return thread
