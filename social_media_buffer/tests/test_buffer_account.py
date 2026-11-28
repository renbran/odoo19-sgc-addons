# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_common import BufferCommon


@tagged("post_install", "-at_install")
class TestBufferAccount(BufferCommon):
    def test_channel_import_is_idempotent(self):
        # Start without channels so the first pass must create every account.
        self.buffer_social_account.unlink()
        channels = [
            {
                "id": "channel-1",
                "name": "first-channel",
                "displayName": "First Channel",
                "service": "linkedin",
                "type": "page",
            },
            {
                "id": "channel-2",
                "name": "second-channel",
                "displayName": "Second Channel",
                "service": "instagram",
                "type": "business",
            },
        ]

        def import_response(*_args, **kwargs):
            query = kwargs["json"]["query"]
            variables = kwargs["json"]["variables"]
            if "query BufferOrganizations" in query:
                self.assertEqual(variables, {})
                return self.buffer_response(
                    {
                        "data": {
                            "account": {
                                "organizations": [
                                    {"id": "org-1", "name": "Organization One"},
                                    {"id": "org-2", "name": "Organization Two"},
                                ]
                            }
                        }
                    }
                )
            if "query BufferChannels" in query:
                self.assertEqual(variables, {"organizationId": "org-1"})
                return self.buffer_response({"data": {"channels": channels}})
            raise AssertionError("Unexpected Buffer operation")

        self.mock_buffer_request.side_effect = import_response
        for _run in range(2):
            action = self.buffer_account.action_import_channels()
            accounts = self.SocialAccount.search(
                [("buffer_account_id", "=", self.buffer_account.id)]
            )
            self.assertEqual(len(accounts), 2)
            self.assertEqual(
                set(accounts.mapped("buffer_channel_id")),
                {"channel-1", "channel-2"},
            )
            self.assertEqual(set(action["domain"][0][2]), set(accounts.ids))
            self.assertTrue(all(account.media_type == "buffer" for account in accounts))

        self.assertEqual(self.mock_buffer_request.call_count, 4)
        first_call = self.mock_buffer_request.call_args_list[0]
        self.assertEqual(first_call.args, ("https://api.buffer.com",))
        self.assertEqual(first_call.kwargs["timeout"], 30)
        self.assertEqual(
            first_call.kwargs["headers"],
            {
                "Authorization": "Bearer test-api-key",
                "Content-Type": "application/json",
            },
        )

    def test_rate_limit_raises_retry_after(self):
        self.answer_buffer({}, status_code=429, headers={"Retry-After": "17"})
        with self.assertRaisesRegex(UserError, "Retry-After: 17"):
            self.buffer_account._buffer_graphql("query { account { id } }")

    def test_graphql_errors_are_user_errors(self):
        self.answer_buffer(
            {
                "data": None,
                "errors": [
                    {
                        "message": "Not authorized",
                        "extensions": {"code": "UNAUTHORIZED"},
                    }
                ],
            }
        )
        with self.assertRaisesRegex(UserError, "UNAUTHORIZED: Not authorized"):
            self.buffer_account._buffer_graphql("query { account { id } }")

    def test_access_token_validation_makes_no_network_call(self):
        self.assertTrue(self.buffer_social_account.validate_access_token())
        self.mock_buffer_request.assert_not_called()
