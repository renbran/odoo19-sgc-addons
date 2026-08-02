# -*- coding: utf-8 -*-
import logging

from odoo import models

from .utils import as_markup, html_to_text

_logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://freellmapi-prod:3001/v1"
DEFAULT_MODEL = "auto"
DEFAULT_MAX_HISTORY = 12
REQUEST_TIMEOUT = 40


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

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
        if not self.livechat_channel_id.sudo().sgc_ai_enabled:
            return
        # Let a scripted chatbot (if any) finish its flow first.
        if self.chatbot_current_step_id:
            return
        if not message or message.message_type != "comment":
            return
        operator = self.livechat_operator_id
        # Skip operator/own messages -> prevents infinite recursion.
        if operator and message.author_id and message.author_id.id == operator.id:
            return
        if not html_to_text(message.body):
            return

        cfg = self._sgc_ai_config()
        if not cfg["api_key"]:
            _logger.warning("SGC live-chat AI: no api_key set; skipping reply.")
            return

        reply = self._sgc_ai_complete(cfg)
        if not reply:
            return
        self.message_post(
            body=as_markup("<p>%s</p>" % reply.replace("\n", "<br/>")),
            author_id=operator.id if operator else False,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )

    # ------------------------------------------------------------------
    def _sgc_ai_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            max_hist = int(icp.get_param("sgc_livechat_ai.max_history") or DEFAULT_MAX_HISTORY)
        except (TypeError, ValueError):
            max_hist = DEFAULT_MAX_HISTORY
        return {
            "endpoint": (icp.get_param("sgc_livechat_ai.endpoint") or DEFAULT_ENDPOINT).strip(),
            "model": (icp.get_param("sgc_livechat_ai.model") or DEFAULT_MODEL).strip(),
            "api_key": (icp.get_param("sgc_livechat_ai.api_key") or "").strip(),
            "system_prompt": icp.get_param("sgc_livechat_ai.system_prompt") or "",
            "max_history": max_hist,
        }

    def _sgc_build_messages(self, cfg):
        """Build the OpenAI-style message list from recent channel history."""
        self.ensure_one()
        operator_id = self.livechat_operator_id.id
        history = self.env["mail.message"].sudo().search(
            [
                ("model", "=", "discuss.channel"),
                ("res_id", "=", self.id),
                ("message_type", "=", "comment"),
            ],
            order="id desc",
            limit=cfg["max_history"],
        )
        msgs = []
        for m in reversed(history):
            text = html_to_text(m.body)
            if not text:
                continue
            is_operator = bool(m.author_id) and m.author_id.id == operator_id
            msgs.append({"role": "assistant" if is_operator else "user", "content": text})
        result = []
        if cfg["system_prompt"]:
            result.append({"role": "system", "content": cfg["system_prompt"]})
        result.extend(msgs)
        return result

    def _sgc_ai_complete(self, cfg):
        """Call the OpenAI-compatible endpoint (freellmapi) and return text."""
        self.ensure_one()
        try:
            from openai import OpenAI
        except ImportError:
            _logger.error("SGC live-chat AI: python 'openai' package not installed.")
            return ""
        messages = self._sgc_build_messages(cfg)
        if not any(m["role"] == "user" for m in messages):
            return ""
        try:
            client = OpenAI(
                api_key=cfg["api_key"],
                base_url=cfg["endpoint"],
                timeout=REQUEST_TIMEOUT,
            )
            resp = client.chat.completions.create(
                model=cfg["model"],
                messages=messages,
                temperature=0.3,
                max_tokens=600,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            _logger.exception("SGC live-chat AI completion failed: %s", e)
            return ""
