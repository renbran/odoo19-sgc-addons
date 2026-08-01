# -*- coding: utf-8 -*-
from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    sgc_ai_enabled = fields.Boolean(
        string="AI Auto-Reply",
        default=False,
        help="When enabled, visitor messages on this live-chat channel are "
        "answered automatically by the selected AI assistant.",
    )
    sgc_ai_assistant_id = fields.Many2one(
        "llm.assistant",
        string="AI Assistant",
        help="LLM assistant used to answer visitors when AI Auto-Reply is on.",
    )
