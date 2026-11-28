# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock, patch

from odoo.addons.social_media_base.tests.test_social_common import (
    TestSocialMediaBaseCommon,
)

PATCH_BUFFER_REQUEST = (
    "odoo.addons.social_media_buffer.models.buffer_account.requests.post"
)


class BufferCommon(TestSocialMediaBaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BufferAccount = cls.env["buffer.account"]
        cls.buffer_account = cls.BufferAccount.create(
            {
                "name": "Buffer test connection",
                "api_key": "test-api-key",
                "organization_id": "org-1",
            }
        )
        cls.buffer_media = cls.env.ref("social_media_buffer.social_media_buffer")
        cls.buffer_social_account = cls.SocialAccount.create(
            {
                "name": "Buffer test channel",
                "media_id": cls.buffer_media.id,
                "remote_ref": "channel-1",
                "buffer_account_id": cls.buffer_account.id,
                "buffer_channel_id": "channel-1",
                "buffer_service": "linkedin",
                "buffer_channel_type": "page",
            }
        )

    def setUp(self):
        super().setUp()
        request_patcher = patch(PATCH_BUFFER_REQUEST)
        self.mock_buffer_request = request_patcher.start()
        self.mock_buffer_request.side_effect = AssertionError(
            "A test attempted a live Buffer API call"
        )
        self.addCleanup(request_patcher.stop)

    @staticmethod
    def buffer_response(payload, status_code=200, headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {}
        response.json.return_value = payload
        return response

    def answer_buffer(self, payload, status_code=200, headers=None):
        self.mock_buffer_request.side_effect = None
        self.mock_buffer_request.return_value = self.buffer_response(
            payload, status_code=status_code, headers=headers
        )
