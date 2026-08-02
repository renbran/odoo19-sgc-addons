# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    sgc_is_ai_bot = fields.Boolean(
        string="AI Live-Chat Bot",
        default=False,
        help="If set, this operator is always considered available for live "
        "chat routing (so the AI can answer visitors 24/7 without a human "
        "being online).",
    )

    def _is_user_available(self):
        # AI bot operators are always available for live-chat routing.
        if self.sgc_is_ai_bot:
            return True
        return super()._is_user_available()
