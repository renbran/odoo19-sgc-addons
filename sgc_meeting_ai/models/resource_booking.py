# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ResourceBookingType(models.Model):
    _inherit = "resource.booking.type"

    sgc_meeting_provider_id = fields.Many2one(
        "sgc.meeting.provider",
        string="Meeting Provider",
        help="Default meeting provider for bookings of this type. "
        "When set, the meeting link is auto-generated from the provider pattern.",
    )


class ResourceBooking(models.Model):
    _inherit = "resource.booking"

    sgc_meeting_provider_id = fields.Many2one(
        "sgc.meeting.provider",
        string="Meeting Provider",
        help="Override the type's default provider for this specific booking.",
    )

    @api.onchange("type_id")
    def _onchange_type_id_set_provider(self):
        for booking in self:
            if booking.type_id and booking.type_id.sgc_meeting_provider_id:
                booking.sgc_meeting_provider_id = (
                    booking.type_id.sgc_meeting_provider_id
                )

    def _prepare_meeting_vals(self):
        vals = super()._prepare_meeting_vals()
        provider = self.sgc_meeting_provider_id or self.type_id.sgc_meeting_provider_id
        if provider and provider.link_pattern and not vals.get("videocall_location"):
            import secrets

            placeholder_id = secrets.token_urlsafe(8).replace("-", "")[:11]
            vals["videocall_location"] = provider.link_pattern.format(
                meeting_id=placeholder_id
            )
        return vals
