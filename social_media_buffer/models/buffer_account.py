# Copyright 2026 Park Group
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import requests

from odoo import fields, models
from odoo.exceptions import UserError

_BUFFER_API_URL = "https://api.buffer.com"
_BUFFER_ORGANIZATIONS_QUERY = """
query BufferOrganizations {
  account {
    organizations {
      id
      name
    }
  }
}
"""
_BUFFER_CHANNELS_QUERY = """
query BufferChannels($organizationId: OrganizationId!) {
  channels(input: {organizationId: $organizationId}) {
    id
    name
    displayName
    descriptor
    service
    type
  }
}
"""


class BufferAccount(models.Model):
    """A Buffer API key and the organization whose channels it imports."""

    _name = "buffer.account"
    _description = "Buffer Account"
    _order = "name, id"

    name = fields.Char(required=True)
    api_key = fields.Char(groups="base.group_system", copy=False)
    organization_id = fields.Char(
        string="Buffer Organization ID",
        help="Restrict channel imports to this Buffer organization. Leave empty "
        "to import the channels of every organization available to the API key.",
    )
    active = fields.Boolean(default=True)
    color = fields.Integer()
    image_1920 = fields.Image()

    def _buffer_graphql(self, query, variables=None):
        """Run one GraphQL operation and return its ``data`` mapping.

        Buffer reports system failures in the top-level ``errors`` list even
        when the HTTP status is 200. Typed mutation errors are deliberately
        left in ``data`` for the publishing helper, which records them on the
        affected publication instead of aborting the other accounts.
        """
        self.ensure_one()
        api_key = self.sudo().api_key
        if not api_key:
            raise UserError(
                self.env._("Configure an API key on the Buffer account first.")
            )
        try:
            response = requests.post(
                _BUFFER_API_URL,
                json={"query": query, "variables": variables or {}},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
        except requests.exceptions.RequestException as error:
            raise UserError(
                self.env._("Could not connect to Buffer: %(error)s", error=error)
            ) from error
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                raise UserError(
                    self.env._(
                        "Buffer rate limit exceeded. Retry-After: %(retry_after)s.",
                        retry_after=retry_after,
                    )
                )
            raise UserError(
                self.env._(
                    "Buffer rate limit exceeded. Check the response headers and "
                    "retry later."
                )
            )
        if response.status_code != 200:
            raise UserError(
                self.env._(
                    "Buffer request failed with HTTP status %(status)s.",
                    status=response.status_code,
                )
            )
        try:
            payload = response.json()
        except ValueError as error:
            raise UserError(
                self.env._("Buffer returned an invalid JSON response.")
            ) from error
        if not isinstance(payload, dict):
            raise UserError(self.env._("Buffer returned an unexpected response."))
        if payload.get("errors"):
            raise UserError(
                self.env._(
                    "Buffer GraphQL error: %(error)s",
                    error=self._buffer_graphql_error_message(payload["errors"]),
                )
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise UserError(self.env._("Buffer returned no GraphQL data."))
        return data

    def _buffer_graphql_error_message(self, errors):
        """Return safe, readable details from Buffer's GraphQL error list."""
        messages = []
        for error in errors if isinstance(errors, list) else [errors]:
            if not isinstance(error, dict):
                messages.append(str(error))
                continue
            message = error.get("message") or self.env._("Unknown Buffer error")
            extensions = error.get("extensions") or {}
            code = extensions.get("code") if isinstance(extensions, dict) else None
            messages.append(f"{code}: {message}" if code else str(message))
        return "; ".join(messages)

    def action_import_channels(self):
        """Create or refresh one ``social.account`` per accessible channel."""
        self.check_access("write")
        SocialAccount = self.env["social.account"]
        media = self.env.ref("social_media_buffer.social_media_buffer")
        imported = SocialAccount.browse()
        for buffer_account in self:
            data = buffer_account._buffer_graphql(_BUFFER_ORGANIZATIONS_QUERY)
            account_data = data.get("account") or {}
            organizations = account_data.get("organizations") or []
            organization_id = (buffer_account.organization_id or "").strip()
            if organization_id:
                organizations = [
                    organization
                    for organization in organizations
                    if str(organization.get("id") or "") == organization_id
                ]
                if not organizations:
                    raise UserError(
                        self.env._(
                            "Buffer organization %(organization)s is not accessible "
                            "with this API key.",
                            organization=organization_id,
                        )
                    )
            for organization in organizations:
                remote_organization_id = organization.get("id")
                if not remote_organization_id:
                    continue
                channel_data = buffer_account._buffer_graphql(
                    _BUFFER_CHANNELS_QUERY,
                    {"organizationId": str(remote_organization_id)},
                )
                for channel in channel_data.get("channels") or []:
                    channel_id = channel.get("id")
                    if not channel_id:
                        raise UserError(
                            self.env._(
                                "Buffer returned a channel without an ID in "
                                "organization %(organization)s.",
                                organization=organization.get("name")
                                or remote_organization_id,
                            )
                        )
                    values = {
                        "name": channel.get("displayName")
                        or channel.get("name")
                        or channel.get("descriptor")
                        or str(channel_id),
                        "username": channel.get("name") or False,
                        "remote_ref": str(channel_id),
                        "buffer_account_id": buffer_account.id,
                        "buffer_channel_id": str(channel_id),
                        "buffer_service": channel.get("service") or False,
                        "buffer_channel_type": channel.get("type") or False,
                        "last_update_account": fields.Datetime.now(),
                    }
                    imported |= SocialAccount._associate_account(
                        "buffer",
                        str(channel_id),
                        values,
                        username=channel.get("name"),
                        create_values={"media_id": media.id},
                    )
        imported._on_account_associated()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "social_media_base.social_account_action"
        )
        action.update(
            {
                "name": self.env._("Imported Buffer Channels"),
                "domain": [("id", "in", imported.ids)],
                "context": {},
                "target": "main",
            }
        )
        return action
