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

    def _sgc_default_reminder_alarm_ids(self):
        """The email + WhatsApp 30-minute reminder alarms shipped as data."""
        alarms = self.env["calendar.alarm"]
        for xmlid in (
            "sgc_meeting_ai.sgc_meeting_reminder_email",
            "sgc_meeting_ai.sgc_meeting_reminder_whatsapp",
        ):
            alarm = self.env.ref(xmlid, raise_if_not_found=False)
            if alarm:
                alarms |= alarm
        return alarms

    def _prepare_meeting_vals(self):
        vals = super()._prepare_meeting_vals()
        if "alarm_ids" not in vals:
            vals["alarm_ids"] = [(6, 0, self._sgc_default_reminder_alarm_ids().ids)]
        provider = self.sgc_meeting_provider_id or self.type_id.sgc_meeting_provider_id
        # google_meet is left untouched here: videocall_location must stay
        # empty so google_calendar's own sync generates a *real* Meet room
        # (conferenceData) for the organizer. Only fabricate a pattern-based
        # link for providers Odoo can't create a real room for itself.
        if (
            provider
            and provider.code != "google_meet"
            and provider.link_pattern
            and not vals.get("videocall_location")
        ):
            import secrets

            placeholder_id = secrets.token_urlsafe(8).replace("-", "")[:11]
            vals["videocall_location"] = provider.link_pattern.format(
                meeting_id=placeholder_id
            )
        return vals
