# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Dedicated always-available calendar so meetings booked at any time of day
# (e.g. early-morning calls across timezones) still "fit" resource_booking's
# scheduling checks.
SGC_247_CALENDAR_NAME = "SGC AI 24/7"

# Map a videocall URL to an sgc.meeting.provider code.
_PROVIDER_URL_HINTS = (
    ("meet.google.com", "google_meet"),
    ("zoom.us", "zoom"),
    ("teams.microsoft.com", "teams"),
    ("teams.live.com", "teams"),
)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    sgc_session_id = fields.Many2one(
        "sgc.meeting.session",
        string="SGC AI Session",
        readonly=True,
    )
    sgc_bot_enabled = fields.Boolean(
        string="AI Bot Auto-Join",
        default=True,
        help="If True, a configured bot service will auto-join this meeting "
        "and produce AI notes.",
    )
    sgc_notes_count = fields.Integer(
        compute="_compute_sgc_notes_count", string="AI Notes"
    )
    sgc_provider_id = fields.Many2one(
        "sgc.meeting.provider",
        string="Meeting Provider",
    )
    sgc_booking_id = fields.Many2one(
        "resource.booking",
        string="Resource Booking",
        readonly=True,
        copy=False,
    )

    def _compute_sgc_notes_count(self):
        for event in self:
            event.sgc_notes_count = self.env["sgc.meeting.notes"].search_count(
                [("session_id.meeting_id", "=", event.id)]
            )

    @api.onchange("sgc_provider_id")
    def _onchange_sgc_provider_id(self):
        # Leave videocall_location empty for google_meet so google_calendar's
        # sync creates a real Meet room instead of a fabricated pattern link.
        if (
            self.sgc_provider_id
            and self.sgc_provider_id.code != "google_meet"
            and self.sgc_provider_id.link_pattern
        ):
            self.videocall_location = self.sgc_provider_id.link_pattern

    # ------------------------------------------------------------------
    # Resource booking integration
    # ------------------------------------------------------------------
    def _sgc_get_247_calendar(self):
        """Return (creating if needed) an always-available resource calendar.

        resource_booking validates that a booking fits inside the working
        intervals of both the booking type's calendar and the resource's
        calendar. A 24/7 calendar guarantees meetings at any hour fit.
        """
        Cal = self.env["resource.calendar"].sudo()
        cal = Cal.search([("name", "=", SGC_247_CALENDAR_NAME)], limit=1)
        if not cal:
            attendances = [
                (
                    0,
                    0,
                    {
                        "name": "All day",
                        "dayofweek": str(day),
                        "hour_from": 0.0,
                        "hour_to": 24.0,
                        "day_period": "morning",
                    },
                )
                for day in range(7)
            ]
            cal = Cal.create({
                "name": SGC_247_CALENDAR_NAME,
                "tz": "UTC",
                "attendance_ids": attendances,
            })
        return cal

    def _get_or_create_booking_type(self):
        calendar = self._sgc_get_247_calendar()
        booking_type = self.env["resource.booking.type"].search([
            ("active", "=", True),
        ], limit=1)
        if not booking_type:
            booking_type = self.env["resource.booking.type"].create({
                "name": "SGC Meeting",
                "combination_assignment": "sorted",
                "resource_calendar_id": calendar.id,
            })
        # Ensure the type accepts bookings at any time of day.
        if booking_type.resource_calendar_id != calendar:
            booking_type.sudo().resource_calendar_id = calendar.id
        return booking_type

    def _sgc_get_or_create_resource(self, user, calendar):
        """Resource representing the meeting organizer (reused if it exists)."""
        Resource = self.env["resource.resource"].sudo()
        resource = Resource.search([
            ("user_id", "=", user.id),
            ("resource_type", "=", "user"),
        ], limit=1)
        if not resource:
            resource = Resource.create({
                "name": user.name,
                "resource_type": "user",
                "user_id": user.id,
                "calendar_id": calendar.id,
                "company_id": (user.company_id or self.env.company).id,
                "tz": user.tz or "UTC",
            })
        return resource

    def _sgc_get_or_create_combination(self, resource, booking_type, calendar):
        """A single-resource combination for the organizer, wired to the type."""
        Combination = self.env["resource.booking.combination"].sudo()
        combination = Combination.search([
            ("resource_ids", "in", resource.ids),
        ]).filtered(lambda c: c.resource_ids == resource)[:1]
        if not combination:
            combination = Combination.create({
                "resource_ids": [(6, 0, resource.ids)],
                "forced_calendar_id": calendar.id,
            })
        elif combination.forced_calendar_id != calendar:
            combination.forced_calendar_id = calendar.id
        if booking_type not in combination.type_rel_ids.mapped("type_id"):
            self.env["resource.booking.type.combination.rel"].sudo().create({
                "type_id": booking_type.id,
                "combination_id": combination.id,
            })
        return combination

    def action_create_resource_booking(self):
        self.ensure_one()
        if self.sgc_booking_id:
            return True

        organizer = self.user_id or self.env.user
        calendar = self._sgc_get_247_calendar()
        booking_type = self._get_or_create_booking_type()
        resource = self._sgc_get_or_create_resource(organizer, calendar)
        combination = self._sgc_get_or_create_combination(
            resource, booking_type, calendar
        )

        attendees = self.partner_ids or organizer.partner_id
        booking = self.env["resource.booking"].create({
            "type_id": booking_type.id,
            "partner_ids": [(6, 0, attendees.ids)],
            "combination_id": combination.id,
            # We assign the resource explicitly; don't let the booking
            # recompute (and possibly clear) it.
            "combination_auto_assign": False,
        })
        # Link to *this* event instead of letting resource_booking spawn a
        # duplicate calendar event. The syncing_booking_ids context suppresses
        # _sync_meeting so the originating event is not overwritten.
        booking.with_context(syncing_booking_ids=booking.ids).write({
            "meeting_id": self.id,
        })
        self.sgc_booking_id = booking.id
        _logger.info(
            "Created resource booking %s (resource %s) for calendar event %s",
            booking.id, resource.id, self.id,
        )
        return True

    # ------------------------------------------------------------------
    # AI meeting session integration
    # ------------------------------------------------------------------
    def _sgc_select_provider(self):
        """Best-guess AI meeting provider from the videocall link."""
        Provider = self.env["sgc.meeting.provider"]
        if self.sgc_provider_id:
            return self.sgc_provider_id
        url = (self.videocall_location or "").lower()
        for hint, code in _PROVIDER_URL_HINTS:
            if hint in url:
                provider = Provider.search([("code", "=", code)], limit=1)
                if provider:
                    return provider
        return (
            Provider.search([("code", "=", "none")], limit=1)
            or Provider.search([], limit=1)
        )

    def _sgc_get_or_create_session(self, bot_enabled=None):
        self.ensure_one()
        session = self.sgc_session_id or self.env["sgc.meeting.session"].search(
            [("meeting_id", "=", self.id)], limit=1
        )
        if bot_enabled is None:
            bot_enabled = self.sgc_bot_enabled
        if not session:
            provider = self._sgc_select_provider()
            session = self.env["sgc.meeting.session"].create({
                "meeting_id": self.id,
                "provider_id": provider.id,
                "bot_enabled": bot_enabled,
            })
            self.sgc_session_id = session.id
        # Ask the bot to join (records intent; real auto-join needs an
        # external bot provider to be configured).
        if bot_enabled and not session.bot_dispatched:
            session.action_dispatch_bot()
        return session

    def action_open_sgc_session(self):
        self.ensure_one()
        session = self._sgc_get_or_create_session()
        return {
            "type": "ir.actions.act_window",
            "name": _("SGC Meeting Session"),
            "res_model": "sgc.meeting.session",
            "view_mode": "form",
            "res_id": session.id,
        }

    # ------------------------------------------------------------------
    # Auto-registration when a salesperson books a meeting
    # ------------------------------------------------------------------
    def _sgc_register_meeting(self):
        """Register opportunity meetings for resource booking + AI recording."""
        for event in self:
            if not event.opportunity_id:
                continue
            if not event.sgc_booking_id:
                try:
                    event.action_create_resource_booking()
                except Exception:
                    _logger.exception(
                        "Failed to create resource booking for event %s",
                        event.id,
                    )
            if not event.sgc_session_id:
                try:
                    event._sgc_get_or_create_session()
                except Exception:
                    _logger.exception(
                        "Failed to create AI meeting session for event %s",
                        event.id,
                    )

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events._sgc_register_meeting()
        return events

    def write(self, vals):
        res = super().write(vals)
        self._sgc_register_meeting()
        return res
