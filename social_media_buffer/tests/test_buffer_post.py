# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta, timezone

from odoo import fields
from odoo.fields import Command
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .test_common import BufferCommon

BASE_PUBLISH_LOGGER = "odoo.addons.social_media_base.models.social_post_account"


@tagged("post_install", "-at_install")
class TestBufferPost(BufferCommon):
    def create_buffer_post(self, **values):
        return self.SocialPost.create(
            dict(
                {
                    "message": "Hello from Odoo",
                    "account_ids": [Command.set(self.buffer_social_account.ids)],
                },
                **values,
            )
        )

    def test_successful_publish_stores_remote_reference(self):
        post = self.create_buffer_post()
        self.answer_buffer(
            {
                "data": {
                    "createPost": {
                        "post": {
                            "id": "post-1",
                            "externalLink": "https://social.example/post-1",
                        }
                    }
                }
            }
        )
        post._action_create_post_account()
        line = post.post_account_ids
        self.assertEqual(line.state, "posted")
        self.assertEqual(line.remote_ref, "post-1")
        self.assertEqual(line.post_account_url, "https://social.example/post-1")
        self.assertEqual(post.state, "published")
        post_input = self.mock_buffer_request.call_args.kwargs["json"]["variables"][
            "input"
        ]
        self.assertEqual(
            post_input,
            {
                "text": "Hello from Odoo",
                "channelId": "channel-1",
                "schedulingType": "automatic",
                "mode": "addToQueue",
            },
        )

    def test_scheduled_publish_uses_custom_scheduled_mode(self):
        post = self.create_buffer_post(
            send_post="schedule",
            send_post_date=fields.Datetime.now() + timedelta(hours=2),
        )
        self.answer_buffer({"data": {"createPost": {"post": {"id": "post-scheduled"}}}})
        post._action_create_post_account()
        post_input = self.mock_buffer_request.call_args.kwargs["json"]["variables"][
            "input"
        ]
        expected_due_at = post.send_post_date.replace(tzinfo=timezone.utc).isoformat(
            timespec="milliseconds"
        )
        self.assertEqual(post_input["mode"], "customScheduled")
        self.assertEqual(post_input["schedulingType"], "automatic")
        self.assertEqual(post_input["dueAt"], expected_due_at.replace("+00:00", "Z"))
        self.assertEqual(post.post_account_ids.state, "posted")

    def test_mutation_error_marks_line_failed(self):
        post = self.create_buffer_post()
        self.answer_buffer({"data": {"createPost": {"message": "Text is too long"}}})
        post._action_create_post_account()
        line = post.post_account_ids
        self.assertEqual(line.state, "failed")
        self.assertFalse(line.remote_ref)
        self.assertIn("Text is too long", line.failed_description)
        self.assertEqual(post.state, "draft")

    def test_missing_post_id_marks_line_failed(self):
        post = self.create_buffer_post()
        self.answer_buffer({"data": {"createPost": {"post": {}}}})
        post._action_create_post_account()
        self.assertEqual(post.post_account_ids.state, "failed")
        self.assertIn(
            "Buffer did not return a post ID",
            post.post_account_ids.failed_description,
        )

    @mute_logger(BASE_PUBLISH_LOGGER)
    def test_attachments_are_rejected_without_an_api_call(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "image.jpg",
                "type": "binary",
                "datas": self.image_base64,
                "mimetype": "image/jpeg",
            }
        )
        post = self.create_buffer_post(image_ids=[Command.set(attachment.ids)])
        post._action_create_post_account()
        self.assertEqual(post.post_account_ids.state, "failed")
        self.assertIn(
            "Buffer media requires a public URL",
            post.post_account_ids.failed_description,
        )
        self.mock_buffer_request.assert_not_called()
