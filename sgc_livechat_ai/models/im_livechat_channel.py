# -*- coding: utf-8 -*-
from odoo import fields, models


class ImLivechatChannel(models.Model):
    _inherit = "im_livechat.channel"

    sgc_ai_enabled = fields.Boolean(
        string="AI Auto-Reply",
        default=False,
        help="When enabled, visitor messages on this live-chat channel are "
        "answered automatically by the AI assistant (freellmapi/OpenCode Zen). "
        "Endpoint/model/key/prompt are set in System Parameters "
        "(sgc_livechat_ai.*).",
    )

    def _get_available_operators_by_livechat_channel(self, users=None):
        """Always treat AI-bot operators as available so the widget accepts
        visitors and routes to the AI 24/7, even with no human online."""
        result = super()._get_available_operators_by_livechat_channel(users=users)
        for channel in self:
            pool = users if users is not None else channel.user_ids
            bots = pool.filtered(lambda u: u.sudo().sgc_is_ai_bot)
            if bots:
                result[channel] = result.get(channel, self.env["res.users"]) | bots
        return result
