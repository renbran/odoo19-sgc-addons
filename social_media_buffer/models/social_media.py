# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SocialMedia(models.Model):
    """Register Buffer as an available social media."""

    _inherit = "social.media"

    # ``social.account.media_type`` is related to this field, so extending the
    # selection here makes the Buffer value available on both models.
    media_type = fields.Selection(
        selection_add=[("buffer", "Buffer")],
        ondelete={"buffer": "cascade"},
    )

    def action_open_account(self):
        res = super().action_open_account()
        if self.media_type == "buffer":
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "social_media_buffer.buffer_account_action"
            )
            action["target"] = "main"
            return action
        return res
