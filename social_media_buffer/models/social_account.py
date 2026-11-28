# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timezone

from odoo import fields, models
from odoo.exceptions import UserError

from ..exceptions import BufferMutationError

_BUFFER_CREATE_POST_MUTATION = """
mutation BufferCreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        externalLink
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


class SocialAccount(models.Model):
    """Buffer channel metadata and post creation."""

    _inherit = "social.account"

    buffer_account_id = fields.Many2one(
        "buffer.account",
        string="Buffer Connection",
        ondelete="set null",
        index=True,
    )
    buffer_channel_id = fields.Char(index=True, copy=False)
    buffer_service = fields.Char()
    buffer_channel_type = fields.Char()

    def validate_access_token(self):
        """Buffer API keys have no expiry date to validate or refresh."""
        buffer_accounts = self.filtered(lambda account: account.media_type == "buffer")
        remaining = self - buffer_accounts
        if remaining:
            return super(SocialAccount, remaining).validate_access_token()
        return True

    def _buffer_create_post(self, message, due_at=None):
        """Create a Buffer post and return its ID and public URL, if known."""
        self.ensure_one()
        if self.media_type != "buffer":
            raise UserError(self.env._("This account is not a Buffer channel."))
        if not self.buffer_account_id or not self.buffer_channel_id:
            raise UserError(
                self.env._(
                    "The Buffer connection and channel ID must be configured "
                    "before publishing."
                )
            )
        post_input = {
            "text": message or "",
            "channelId": self.buffer_channel_id,
            "schedulingType": "automatic",
            "mode": "customScheduled" if due_at else "addToQueue",
        }
        if due_at:
            due_date = fields.Datetime.to_datetime(due_at)
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            else:
                due_date = due_date.astimezone(timezone.utc)
            post_input["dueAt"] = due_date.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            )
        data = self.buffer_account_id._buffer_graphql(
            _BUFFER_CREATE_POST_MUTATION, {"input": post_input}
        )
        result = data.get("createPost") or {}
        post = result.get("post") or {}
        if not post and result.get("message"):
            raise BufferMutationError(
                self.env._(
                    "Buffer refused the post: %(error)s", error=result["message"]
                )
            )
        post_id = post.get("id")
        if not post_id:
            return False, False
        return str(post_id), post.get("externalLink") or False
