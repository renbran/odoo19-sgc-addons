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
    # Shared Google Meet organizer for CRM/SDR customer meetings
    # ------------------------------------------------------------------
    def _sgc_get_meet_organizer(self):
        """Odoo user whose connected Google Calendar should generate the
        real Meet room for CRM meetings, so individual SDRs don't each
        need their own Google OAuth connection. Configurable via
        ir.config_parameter 'sgc_meeting_ai.meet_organizer_login'.
        """
        login = self.env["ir.config_parameter"].sudo().get_param(
            "sgc_meeting_ai.meet_organizer_login"
        )
        if not login:
            _logger.warning(
                "sgc_meeting_ai.meet_organizer_login is not set: CRM meetings "
                "keep their own organizer and will NOT get a real Google Meet "
                "room. Set it to the login of a user with a connected Google "
                "Calendar."
            )
            return self.env["res.users"]
        organizer = self.env["res.users"].sudo().search(
            [("login", "=", login)], limit=1
        )
        if not organizer:
            _logger.warning(
                "sgc_meeting_ai.meet_organizer_login is set to %r but no such "
                "user exists: CRM meetings will NOT get a real Google Meet room.",
                login,
            )
            return organizer
        # Fail *visibly* rather than silently: without a Google token the
        # reassignment still happens and nothing errors, but no Meet room is
        # ever created -- historically the hardest symptom here to diagnose.
        if "google_calendar_rtoken" in organizer._fields and not organizer.sudo().google_calendar_rtoken:
            _logger.warning(
                "Meet organizer %r has no connected Google Calendar "
                "(no refresh token): meetings will be reassigned but will NOT "
                "get a real Google Meet room until it is re-authorized.",
                login,
            )
        return organizer

    def _sgc_apply_meet_organizer(self):
        """Reassign the organizer of CRM/SDR customer meetings to the
        shared Meet organizer, keeping the actual salesperson as an
        attendee, so the meeting gets a real Google Meet room without
        requiring every SDR to connect their own Google account.
        """
        organizer = self._sgc_get_meet_organizer()
        if not organizer:
            return
        for event in self:
            if event.user_id == organizer:
                continue
            # The shared organizer must also be an *attendee*, not just
            # user_id: google_calendar._get_sync_domain() selects events with
            # ('partner_ids.user_ids', 'in', env.user.id), so an event that
            # only names crm@sgctech.ai as organizer is never picked up by its
            # Google sync -- and a real Meet room is therefore never created.
            attendee_partners = (
                event.partner_ids
                | event.user_id.partner_id
                | organizer.partner_id
            )
            event.with_context(sgc_applying_meet_organizer=True).write({
                "partner_ids": [(6, 0, attendee_partners.ids)],
                "user_id": organizer.id,
            })

    def _sgc_clear_discuss_videocall(self):
        """Drop Odoo's native Discuss videocall link before the first Google sync.

        google_calendar only asks Google to create a real Meet room when the
        event has no videocall_location and no location at insert time (see
        google_calendar/models/calendar.py: conferenceData createRequest).
        A Discuss auto-link suppresses that, which is why meetings kept showing
        an app.sgctech.ai/calendar/join_videocall/... URL instead of a
        meet.google.com room. Only Discuss links are dropped -- a deliberate
        Zoom/Teams/custom link is left untouched -- and only before the event
        has been synced, so an existing Google conference is never stripped.
        """
        for event in self:
            location = event.videocall_location or ""
            if not location or self.DISCUSS_ROUTE not in location:
                continue
            if "google_id" in event._fields and event.google_id:
                continue
            event.with_context(sgc_applying_meet_organizer=True).write({
                "videocall_location": False,
            })

    # ------------------------------------------------------------------
    # Immediate Google push (Meet room + Google Calendar entry)
    # ------------------------------------------------------------------
    @staticmethod
    def _sgc_extract_meet_url(google_values):
        """Pull the Meet URL out of a Google event resource, if it has one."""
        if not google_values:
            return False
        url = google_values.get("hangoutLink")
        if url:
            return url
        conference = google_values.get("conferenceData") or {}
        for entry in conference.get("entryPoints") or []:
            if entry.get("entryPointType") == "video" and entry.get("uri"):
                return entry["uri"]
        return False

    def _get_post_sync_values(self, request_values, google_values):
        """Also store the Meet URL Google just created for this event.

        Upstream throws ``google_values`` away apart from the event id, so the
        ``hangoutLink`` that comes back from the ``conferenceData.createRequest``
        we sent is discarded, and ``videocall_location`` is only ever filled on a
        later Google -> Odoo pass. Since the sync cron on this database runs
        every 12h, that meant attendees waited up to a *day* for the invitation
        carrying the Meet link. Capturing the URL here puts it in the very same
        write that stores ``google_id``, which fires the re-send hook in
        ``write()`` below, so the branded invitation goes out with a working
        Meet link seconds after the booking.

        ``need_sync: False`` is already in ``values``, so adding a synced field
        here does not flip ``need_sync`` back on (see ``google_sync.write()``)
        and therefore cannot cause a patch loop back to Google.
        """
        values = super()._get_post_sync_values(request_values, google_values)
        if not self.videocall_location:
            meet_url = self._sgc_extract_meet_url(google_values)
            if meet_url:
                values["videocall_location"] = meet_url
        return values

    def _sgc_push_to_google(self):
        """Insert CRM meetings into the Meet organizer's Google Calendar now.

        ``google_sync.create()`` does attempt an insert, but it runs inside
        ``super().create()`` -- i.e. *before* ``_sgc_apply_meet_organizer`` has
        moved the event onto the shared Meet organizer and before
        ``_sgc_clear_discuss_videocall`` has dropped the Discuss link. At that
        moment the organizer is still the salesperson, who has no Google token,
        so ``_google_insert`` silently does nothing. ``google_sync.write()``
        then only ever *patches* records that already carry a ``google_id`` --
        it never inserts -- so the now-correct event is left untouched until the
        "Google Calendar: synchronization" cron sweeps it up, and that cron runs
        only every 12 hours. That gap is why bookings appeared neither in Google
        Calendar nor with a Meet link: nothing was pushing them.
        """
        if "google_id" not in self._fields:
            return  # google_calendar is not installed
        try:
            from odoo.addons.google_calendar.utils.google_calendar import (
                GoogleCalendarService,
            )
        except ImportError:  # pragma: no cover - defensive
            return

        # A cursor lives exactly as long as the transaction, which is the right
        # scope for this guard: _google_insert defers the real API call to
        # post-commit, so two writes in one transaction would both still see an
        # empty google_id and queue a second insert -- creating a duplicate
        # event in Google Calendar.
        pushed = getattr(self.env.cr, "_sgc_google_pushed", None)
        if pushed is None:
            pushed = set()
            self.env.cr._sgc_google_pushed = pushed

        service = None
        for event in self:
            if event.google_id or event.id in pushed:
                continue
            if not event._sgc_is_customer_meeting():
                continue
            organizer = event.user_id
            if not organizer or not organizer.sudo().google_calendar_rtoken:
                continue
            if organizer.sudo()._get_google_sync_status() != "sync_active":
                _logger.warning(
                    "Meet organizer %s is not actively synced with Google: "
                    "meeting %s will not get a Meet room until the sync cron "
                    "runs.",
                    organizer.login, event.id,
                )
                continue
            if event.videocall_location or event.location:
                # google_calendar only asks Google for a Meet room when *both*
                # are empty -- see google_calendar/models/calendar.py, the
                # conferenceData createRequest is skipped otherwise. Worth
                # saying out loud: a salesperson typing anything into Location
                # silently costs them the Meet link.
                _logger.warning(
                    "Meeting %s has %s set, so Google will create the calendar "
                    "entry but NOT a Meet room.",
                    event.id,
                    "a videocall link" if event.videocall_location else "a location",
                )
            if service is None:
                service = GoogleCalendarService(self.env["google.service"])
            event_as_organizer = event.with_user(organizer)
            try:
                event_as_organizer._google_insert(
                    service, event_as_organizer._google_values(), timeout=3
                )
            except Exception:
                _logger.exception(
                    "Failed to push CRM meeting %s to Google Calendar", event.id
                )
            else:
                pushed.add(event.id)

    # ------------------------------------------------------------------
    # Auto-registration when a salesperson books a meeting
    # ------------------------------------------------------------------
    def _sgc_is_customer_meeting(self):
        """True for meetings that should get a shared Google Meet room.

        A CRM booking always qualifies. Beyond those, a meeting qualifies as
        soon as one attendee is *not* an internal employee -- i.e. there is a
        customer or prospect in the room -- which covers meetings booked
        straight from the Calendar app rather than from an opportunity. A
        partner with no user account, or only portal/share users, is external.

        Internal stand-ups and personal time blocks have employee-only
        attendees, so they keep their own organizer and stay off the shared
        crm@sgctech.ai calendar.
        """
        self.ensure_one()
        if "opportunity_id" in self._fields and self.opportunity_id:
            return True
        organizer_partner = self.user_id.partner_id
        for partner in self.partner_ids - organizer_partner:
            users = partner.sudo().user_ids
            if not users or all(user.share for user in users):
                return True
        return False

    def _sgc_register_meeting(self):
        """Register opportunity meetings for resource booking + AI recording,
        and route every customer meeting through the shared Meet organizer."""
        for event in self:
            # Resource booking + AI session stay strictly CRM-scoped: they key
            # off the opportunity and would otherwise spawn bookings/sessions
            # for every externally-attended meeting in the database.
            if not event.opportunity_id:
                continue
            # Resource booking/session must use the *real* salesperson so
            # each SDR keeps their own always-available resource. Swapping
            # the Meet organizer first would make every CRM meeting share
            # crm@sgctech.ai's single resource (and its limited working
            # hours), causing "no resource valid" booking failures.
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
        # Applied last, in its own pass, and over a wider set than the CRM
        # bookings above: this only touches the event's own organizer and
        # attendees, never the resource booking, so it cannot affect resource
        # validity.
        if self.env.context.get("sgc_applying_meet_organizer"):
            return
        for event in self:
            if not event._sgc_is_customer_meeting():
                continue
            # An event that arrived *from* Google already has a real organizer
            # over there. Reassigning it would patch that change straight back
            # and hijack somebody's own meeting -- this matters now that the
            # scope is every externally-attended meeting, not just CRM
            # bookings, since inbound sync creates plenty of those.
            if "google_id" in event._fields and event.google_id:
                continue
            try:
                event._sgc_apply_meet_organizer()
            except Exception:
                _logger.exception(
                    "Failed to apply shared Meet organizer for event %s",
                    event.id,
                )
            try:
                event._sgc_clear_discuss_videocall()
            except Exception:
                _logger.exception(
                    "Failed to clear Discuss videocall link for event %s",
                    event.id,
                )

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events._sgc_register_meeting()
        # Only after _sgc_register_meeting(): the push has to happen once the
        # organizer is the shared Meet account and the Discuss link is gone,
        # otherwise Google is asked to create the event on behalf of a user
        # with no token and without a conference request.
        events._sgc_push_to_google()
        return events

    def write(self, vals):
        # Detect when google_calendar sync populates a real Google Meet URL
        # AFTER the initial invitation was already sent (with empty/Discuss
        # videocall_location). Re-send the invitation so attendees get the
        # Meet link that didn't exist at first send. Capture pre-write state
        # BEFORE super().write() so we can detect the transition.
        resend_events = self.env["calendar.event"]
        if "videocall_location" in vals:
            new_loc = vals.get("videocall_location") or ""
            if "meet.google.com" in new_loc:
                for event in self:
                    if not event._sgc_is_customer_meeting():
                        continue
                    old_loc = event._origin.videocall_location or ""
                    if "meet.google.com" not in old_loc:
                        resend_events |= event
        res = super().write(vals)
        if resend_events:
            try:
                resend_events.attendee_ids._send_invitation_emails()
            except Exception:
                _logger.exception(
                    "Failed to re-send CRM invitation with Meet link for events %s",
                    resend_events.ids,
                )
        self._sgc_register_meeting()
        # A meeting linked to its opportunity after creation reaches the same
        # state a fresh CRM booking does, and would otherwise wait for the 12h
        # cron. The internal writes made by _sgc_register_meeting carry
        # sgc_applying_meet_organizer, so this does not re-enter on those.
        if not self.env.context.get("sgc_applying_meet_organizer"):
            self._sgc_push_to_google()
        return res
