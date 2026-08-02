# -*- coding: utf-8 -*-
from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    sgc_ai_enabled = fields.Boolean(
        string="AI Auto-Reply",
        default=False,
        help="When enabled, visitor messages on this live-chat channel are "
        "answered automatically by the AI assistant (freellmapi). "
        "Endpoint/model/key/prompt are set in System Parameters "
        "(sgc_livechat_ai.*).",
    )
