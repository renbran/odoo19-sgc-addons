# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError

from ..exceptions import BufferMutationError


class SocialPostAccount(models.Model):
    """Publish Odoo posts on their Buffer channels."""

    _inherit = "social.post.account"

    def _action_post(self, post_id):
        res = super()._action_post(post_id)
        if any(account.media_type == "buffer" for account in post_id.account_ids):
            post_accounts = post_id._filter_by_media_types(["buffer"])
            images, videos = post_id._medias_for_publication()
            for post_account in post_accounts:
                with post_account._publish_guard():
                    post_account._check_publishable()
                    if images or videos:
                        raise UserError(
                            self.env._(
                                "Buffer media requires a public URL. Image and "
                                "video attachments are not supported in phase 1; "
                                "remove them from this Buffer post."
                            )
                        )
                    try:
                        remote_ref, post_url = post_account._publish_attempt(
                            post_account.account_id._buffer_create_post,
                            message=post_account.message,
                            due_at=post_id.send_post_date,
                        )
                    except BufferMutationError as error:
                        post_account._register_publish_refused(str(error))
                        continue
                    if remote_ref:
                        post_account._register_publish_success(
                            remote_ref, post_url, {}, False
                        )
                    else:
                        post_account._register_publish_refused(
                            self.env._(
                                "Buffer did not return a post ID. The publication "
                                "was not confirmed."
                            )
                        )
        return res
