# -*- coding: utf-8 -*-
import logging

from odoo import models

from .utils import html_to_text

_logger = logging.getLogger(__name__)


class LLMThread(models.Model):
    _inherit = "llm.thread"

    def sgc_generate_reply(self, user_text):
        """Run the assistant for one visitor turn and return the reply HTML.

        `generate()` is a generator that posts the assistant answer into this
        thread as a mail.message with llm_role='assistant'. We exhaust it, then
        read back the latest assistant message body (already markdown->HTML).
        """
        self.ensure_one()
        if not user_text:
            return ""
        # Exhaust the generation stream (runs the LLM + any tool calls).
        for _event in self.generate(user_message_body=user_text):
            pass
        msg = self.env["mail.message"].sudo().search(
            [
                ("model", "=", "llm.thread"),
                ("res_id", "=", self.id),
                ("llm_role", "=", "assistant"),
                ("is_error", "=", False),
            ],
            order="id desc",
            limit=1,
        )
        return msg.body or "" if msg else ""

    @staticmethod
    def _sgc_html_to_text(body):
        return html_to_text(body)
