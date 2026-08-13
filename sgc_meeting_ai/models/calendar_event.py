# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import time
from uuid import UUID, uuid4, uuid5

import requests

from odoo import _, api, fields, models
from odoo.tools import email_normalize

# Stable namespace for deriving deterministic Meet conferenceData
# requestIds from our own event ids -- so a retried insert reuses the
# same requestId instead of minting a second, orphaned conference.
_SGC_REQUEST_ID_NAMESPACE = UUID("6f1b6c1e-6e6b-4a5a-9b0a-2f6c5b3a9d10")

# Per-worker-process MX lookup cache (module-level, not self.pool -- Registry
# has no dict-like setdefault). Domain -> True/False, keyed by lowercased
# domain string; failures are deliberately never cached (see
# _sgc_domain_is_google_hosted).
_SGC_GOOGLE_MX_CACHE = {}

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
    sgc_attendee_domain_advisory = fields.Selection(
        [
            ("clear", "All attendee domains resolved, none flagged"),
            ("flagged", "Possibly non-Google attendee domain"),
            ("unknown", "MX lookup failed for one or more domains"),
        ],
        string="Attendee Domain Advisory",
        compute="_compute_sgc_attendee_domain_advisory",
        help="Best-effort, advisory-only signal -- do not branch logic on "
        "this field. There is no API that answers 'does this address have "
        "a Google account' (Google blocks that deliberately to prevent "
        "account enumeration), so this can only check whether an "
        "attendee's domain is Google-*hosted* (MX resolves to Google's "
        "mail servers), which covers Gmail and any Workspace domain. It "
        "CANNOT detect a personal Google account registered on a "
        "non-Google-hosted address (e.g. an outlook.com address with a "
        "Google account attached) -- those show as flagged even though "
        "they may join fine, and conversely nothing here guarantees a "
        "Google-hosted address's owner will actually sign into that exact "
        "account when joining. The waiting-room bypass depends on the "
        "guest signing into Meet with the invited address; this field is "
        "a hint for support triage, not a predictor of that outcome. "
        "'unknown' means MX resolution failed (timeout/NXDOMAIN/resolver "
        "error) for at least one attendee domain -- it is NOT evidence "
        "the domain is non-Google, just that we could not check.",
    )

    @api.model
    def _sgc_domain_is_google_hosted(self, domain):
        """MX-based check: does `domain` route mail through Google?

        Cached per-domain for the life of the worker process -- MX records
        for a real mail domain essentially never change, and this avoids a
        DNS round-trip on every form load. Returns None (not False) on a
        lookup failure so a transient DNS hiccup doesn't get recorded as
        a false "not Google" -- callers should treat None as "unknown",
        not "no".
        """
        if domain in _SGC_GOOGLE_MX_CACHE:
            return _SGC_GOOGLE_MX_CACHE[domain]
        try:
            import dns.resolver
            answer = dns.resolver.resolve(domain, "MX", lifetime=3)
            is_google = any(
                str(r.exchange).rstrip(".").endswith("google.com")
                for r in answer
            )
        except Exception:
            # NXDOMAIN, timeout, no MX record, dnspython not installed,
            # etc -- all "unknown", not "not Google". Don't cache failures:
            # a transient DNS blip shouldn't stick for the worker's lifetime.
            return None
        _SGC_GOOGLE_MX_CACHE[domain] = is_google
        return is_google

    @api.depends("partner_ids.email")
    def _compute_sgc_attendee_domain_advisory(self):
        for event in self:
            flagged = False
            saw_unknown = False
            for partner in event.partner_ids:
                email = (partner.email or "").lower().strip()
                if not email or "@" not in email:
                    continue
                domain = email.rsplit("@", 1)[-1]
                is_google = event._sgc_domain_is_google_hosted(domain)
                if is_google is None:
                    saw_unknown = True
                elif is_google is False:
                    flagged = True
            if flagged:
                event.sgc_attendee_domain_advisory = "flagged"
            elif saw_unknown:
                event.sgc_attendee_domain_advisory = "unknown"
            else:
                event.sgc_attendee_domain_advisory = "clear"

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
        # sudo like every other helper here: booking registration is a
        # side effect of saving a meeting, so it runs as whoever happens to
        # touch the event -- a salesperson, or crm@sgctech.ai when the Google
        # sync writes back. Neither has resource_booking rights, and without
        # this the whole registration dies on "Access Denied by ACLs for
        # operation: read, uid: 111, model: resource.booking.type", caught and
        # logged as a bare "Failed to create resource booking".
        BookingType = self.env["resource.booking.type"].sudo()
        booking_type = BookingType.search([
            ("active", "=", True),
        ], limit=1)
        if not booking_type:
            booking_type = BookingType.create({
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
        # resource.booking.start is a *settable* stored field computed from
        # meeting_id.start, so a default_start left in the context by whatever
        # view the salesperson booked from silently seeds it. _sync_meeting()
        # then sees a booking with a start but no meeting_id and lazily creates
        # a SECOND calendar.event, which re-enters our create() override and
        # books again -- the loop behind triplicated meetings and the
        # "Cannot schedule these bookings" wall of duplicates. Passing the
        # context positionally *replaces* it rather than merging, dropping
        # every default_* key in one go.
        booking_context = {
            key: value
            for key, value in self.env.context.items()
            if not key.startswith("default_")
        }
        booking_context["sgc_skip_meeting_register"] = True
        booking = self.env["resource.booking"].sudo().with_context(booking_context).create({
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

    def _sgc_sessions(self):
        """Every AI session attached to these events.

        ``sgc_session_id`` is a denormalized convenience pointer and is not
        guaranteed to be set (a session created directly on
        ``sgc.meeting.session`` never fills it in), so the meeting link is the
        authoritative side of the relation. Anything that has to find the
        notetaker for an event must go through here.
        """
        sessions = self.env["sgc.meeting.session"].search(
            [("meeting_id", "in", self.ids)]
        )
        return sessions | self.sgc_session_id

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
        organizer._sgc_ensure_google_sync_enabled()
        return organizer

    def _sgc_get_meet_cohost_partner(self):
        """Human fallback attendee added to every customer meeting.

        The shared Meet organizer (crm@sgctech.ai) is a non-Workspace
        Google account, so Meet's Space API can't grant it accessType=OPEN
        (confirmed: PERMISSION_DENIED on spaces it created itself) --
        customers are stuck on the host-approval waiting room with nobody
        watching to let them in. Until that account is upgraded to Google
        Workspace, keep a real person on every invite as an attendee who
        can actually admit guests. Configurable via ir.config_parameter
        'sgc_meeting_ai.meet_cohost_email'.
        """
        email = self.env["ir.config_parameter"].sudo().get_param(
            "sgc_meeting_ai.meet_cohost_email"
        )
        if not email:
            return self.env["res.partner"]
        partner = self.env["res.partner"].sudo().search(
            [("email", "=", email)], limit=1
        )
        if not partner:
            _logger.warning(
                "sgc_meeting_ai.meet_cohost_email is set to %r but no "
                "matching partner exists: meetings will not include the "
                "fallback human attendee.", email,
            )
        return partner

    def _sgc_apply_meet_organizer(self):
        """Reassign the organizer of CRM/SDR customer meetings to the
        shared Meet organizer, keeping the actual salesperson as an
        attendee, so the meeting gets a real Google Meet room without
        requiring every SDR to connect their own Google account.
        """
        organizer = self._sgc_get_meet_organizer()
        if not organizer:
            return
        cohost = self._sgc_get_meet_cohost_partner()
        for event in self:
            if event.user_id == organizer and cohost in event.partner_ids:
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
                | cohost
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
        """Pull the Meet URL out of a Google event resource, if it has one.

        conferenceData.entryPoints is the source of truth for the join link
        Meet actually trusts attendees on; hangoutLink is a legacy mirror
        Google keeps for backward compatibility and is only used here if
        entryPoints is somehow absent.
        """
        if not google_values:
            return False
        conference = google_values.get("conferenceData") or {}
        for entry in conference.get("entryPoints") or []:
            if entry.get("entryPointType") == "video" and entry.get("uri"):
                return entry["uri"]
        return google_values.get("hangoutLink") or False

    @staticmethod
    def _sgc_conference_status(google_values):
        """conferenceData.createRequest.status.statusCode, if present.

        Google creates the Meet conference asynchronously: the insert
        response can come back with status "pending" and no entryPoints
        yet. Returns False when there is no createRequest status to read
        (e.g. the conference already existed, or this isn't a createRequest
        response at all).
        """
        if not google_values:
            return False
        create_request = (
            (google_values.get("conferenceData") or {}).get("createRequest")
            or {}
        )
        return (create_request.get("status") or {}).get("statusCode") or False

    def _sgc_poll_conference(self, google_values, event_id):
        """Google creates the Meet conference asynchronously: right after
        insert, conferenceData.createRequest.status.statusCode can still be
        "pending" with no entryPoints. Poll events.get (conferenceDataVersion=1)
        with short backoff until it flips to "success" (join link ready) or
        "failure" (explicitly give up -- never silently return an unconfirmed
        booking), or we exhaust attempts and log a warning.

        Runs inside the same @after_commit deferred call as the original
        insert (see google_sync._google_insert), so a bounded sleep here
        blocks only that background callback, not the request/transaction
        that created the booking.
        """
        status = self._sgc_conference_status(google_values)
        if status != "pending":
            return google_values
        organizer = self.user_id
        if not organizer or not organizer.sudo().google_calendar_rtoken:
            return google_values
        try:
            token = organizer.sudo()._get_google_calendar_token()
        except Exception:
            _logger.exception(
                "Could not get Google token to poll conference status "
                "for event %s", self.id,
            )
            return google_values
        if not token:
            return google_values

        url = (
            f"https://www.googleapis.com/calendar/v3/calendars/primary/"
            f"events/{event_id}?conferenceDataVersion=1"
        )
        headers = {"Authorization": f"Bearer {token}"}
        delay = 1.0
        for attempt in range(1, 6):
            time.sleep(delay)
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                polled = resp.json()
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else None
                _logger.warning(
                    "Conference status poll for event %s failed (%s) on "
                    "attempt %s/5: %s",
                    self.id, code, attempt, e,
                )
                continue
            except Exception:
                _logger.exception(
                    "Conference status poll for event %s failed on "
                    "attempt %s/5", self.id, attempt,
                )
                continue
            status = self._sgc_conference_status(polled)
            if status == "success":
                return polled
            if status == "failure":
                _logger.error(
                    "Google Meet conference creation FAILED for event %s "
                    "(conferenceData.createRequest.status.statusCode == "
                    "'failure'). Booking will NOT have a Meet link.",
                    self.id,
                )
                return polled
            delay = min(delay * 1.5, 3.0)
        _logger.warning(
            "Conference for event %s still 'pending' after 5 polling "
            "attempts; Meet link not yet available, will pick up on the "
            "next sync pass.",
            self.id,
        )
        return google_values

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
        event_id = request_values.get("id") or google_values.get("id")
        if self._sgc_conference_status(google_values) == "pending" and event_id:
            google_values = self._sgc_poll_conference(google_values, event_id)
        if not self.videocall_location:
            meet_url = self._sgc_extract_meet_url(google_values)
            if meet_url:
                values["videocall_location"] = meet_url
            elif self._sgc_conference_status(google_values) == "failure":
                _logger.error(
                    "Event %s synced to Google without a Meet link "
                    "(conference creation failed). Not marking a booking "
                    "confirmed on a broken link -- check manually.",
                    self.id,
                )
        conference_id = (
            (google_values or {}).get("conferenceData") or {}
        ).get("conferenceId")
        if conference_id:
            self._sgc_set_meet_open_access(conference_id)
        return values

    @staticmethod
    def _sgc_extract_conference_id(meet_url):
        """meet.google.com/xxx-xxxx-xxx -> xxx-xxxx-xxx (== Meet API space id)."""
        if not meet_url or "meet.google.com/" not in meet_url:
            return False
        tail = meet_url.split("meet.google.com/", 1)[1]
        code = tail.split("?", 1)[0].strip("/")
        return code or False

    @api.model
    def _sgc_workspace_mode_enabled(self):
        """Feature flag for the Meet REST API (spaces.patch accessType=OPEN)
        path. Default OFF: that API is Workspace-only and 403s outright on
        crm@sgctech.ai's free Google account (confirmed: "Permission denied
        on resource Space" even on spaces it created itself, with a token
        holding meetings.space.settings). The Calendar-API attendee-trust
        path (_sgc_apply_meet_organizer + deterministic conferenceData
        createRequest below) is what actually removes the waiting room on
        a free account. Flip 'sgc_meeting_ai.workspace_mode' to 'true' in
        ir.config_parameter if this account is ever upgraded to Workspace.
        """
        return self.env["ir.config_parameter"].sudo().get_param(
            "sgc_meeting_ai.workspace_mode", "false"
        ).lower() in ("1", "true", "yes")

    def _sgc_set_meet_open_access(self, conference_id):
        """Disable Meet's host-approval waiting room for the shared
        organizer's rooms, so customers/SDRs join instantly instead of
        waiting on crm@sgctech.ai -- a service account nobody is watching --
        to admit them.

        Requires the organizer's Google connection to include the
        meetings.space.settings scope (see google_calendar_meet_scope.py).
        A token from before that scope was added will 403 here; this
        silently logs and moves on rather than blocking the booking, since
        the calendar entry and Meet room themselves are still valid.

        Gated by _sgc_workspace_mode_enabled(): on a free/personal Google
        account this API is unreachable no matter what, so calling it is
        pure log noise. Left in place, not deleted, for when/if the
        organizer account is upgraded to Workspace.
        """
        if not self._sgc_workspace_mode_enabled():
            return
        organizer = self.user_id
        if not organizer or not organizer.sudo().google_calendar_rtoken:
            return
        try:
            token = organizer.sudo()._get_google_calendar_token()
        except Exception:
            _logger.exception(
                "Could not get Google token to set Meet open access "
                "for event %s", self.id,
            )
            return
        if not token:
            return
        url = (
            f"https://meet.googleapis.com/v2/spaces/{conference_id}"
            "?updateMask=config.accessType"
        )
        try:
            resp = requests.patch(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"config": {"accessType": "OPEN"}},
                timeout=10,
            )
            if resp.status_code >= 400:
                _logger.warning(
                    "Could not set Meet space %s to OPEN access (%s): %s. "
                    "Organizer %s may need to reconnect Google Calendar to "
                    "grant the new Meet scopes.",
                    conference_id, resp.status_code, resp.text, organizer.login,
                )
            else:
                _logger.info(
                    "Meet space %s set to OPEN access (event %s)",
                    conference_id, self.id,
                )
        except Exception:
            _logger.exception(
                "Failed to set Meet open access for space %s (event %s)",
                conference_id, self.id,
            )

    @api.model
    def _sgc_backfill_meet_open_access(self, limit=None):
        """One-off/cron-callable: apply OPEN access to every existing
        customer meeting that already has a real Meet room, so meetings
        booked before this fix shipped stop waiting on the host too.
        Returns (attempted, skipped_no_token) counts for a status message.
        """
        domain = [
            ("videocall_location", "like", "meet.google.com/"),
            ("user_id.google_calendar_rtoken", "!=", False),
        ]
        events = self.search(domain, limit=limit)
        attempted = 0
        skipped = 0
        for event in events:
            conference_id = event._sgc_extract_conference_id(
                event.videocall_location
            )
            if not conference_id:
                skipped += 1
                continue
            event._sgc_set_meet_open_access(conference_id)
            attempted += 1
        _logger.info(
            "Meet open-access backfill: attempted %s, skipped %s (no "
            "extractable conference id) out of %s matching events",
            attempted, skipped, len(events),
        )
        return attempted, skipped

    def _skip_send_mail_status_update(self):
        """Keep sending the SGC invitation even while Google sync is active.

        google_calendar suppresses Odoo's *own* invitation emails whenever the
        organizer has a working Google connection, on the assumption that
        Google will invite the attendees instead
        (``google_calendar/models/calendar.py::_skip_send_mail_status_update``).

        For SGC that silently defeats the entire branded-invitation feature:
        every customer meeting is deliberately routed through crm@sgctech.ai,
        which by design *always* has a live Google connection. So the moment
        sync was repaired, attendees stopped receiving the SGC template and got
        Google's plain "Invitation to ..." mail instead. The two features
        undo each other, and the loser is the one nobody notices, because an
        invitation still arrives -- just the wrong one.
        """
        if self and self._sgc_is_customer_meeting():
            return False
        return super()._skip_send_mail_status_update()

    def _sgc_conference_request_id(self):
        """Deterministic requestId for conferenceData.createRequest, derived
        from our own event id rather than a fresh uuid4() per call.

        _google_insert runs @after_commit and can legitimately be retried
        (network hiccup, worker restart before the deferred call completes);
        a random requestId on retry asks Google to mint a SECOND, orphaned
        Meet room for the same booking. Google dedupes createRequest by
        requestId, so reusing the same one derived from event.id makes a
        retry idempotent instead.
        """
        self.ensure_one()
        return str(uuid5(_SGC_REQUEST_ID_NAMESPACE, f"sgc-meeting-event-{self.id}"))

    def _google_values(self):
        """Ask Google for a Meet room even when the meeting has a Location.

        Google only auto-creates a conference when ``videocall_location`` and
        ``location`` are BOTH empty, so a salesperson typing anything sensible
        into Location -- "Online Meeting", "Zoom", "Client office" -- silently
        costs the meeting its Meet room, with no error anywhere. Requesting the
        conference explicitly makes Location a free-text note again instead of
        a hidden switch that disables video.

        Only for customer meetings, only on first insert, and never when a
        deliberate videocall link is already set.

        Also overrides whatever requestId upstream (or our own branch below)
        picked, with a deterministic one -- see _sgc_conference_request_id.
        """
        values = super()._google_values()
        if (
            "google_id" in self._fields
            and not self.google_id
            and not self.videocall_location
            and self.location
            and not values.get("conferenceData")
            and self._sgc_is_customer_meeting()
        ):
            values["conferenceData"] = {"createRequest": {"requestId": uuid4().hex}}
        if (values.get("conferenceData") or {}).get("createRequest"):
            values["conferenceData"]["createRequest"]["requestId"] = (
                self._sgc_conference_request_id()
            )
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
    def _sgc_get_opportunity_attendee(self):
        """The customer who should be invited to this opportunity's meeting.

        Odoo only auto-invites ``lead.partner_id``
        (``crm_lead.action_schedule_meeting``), so an opportunity that was
        never converted to a linked contact invites nobody -- the salesperson
        has to remember to add the customer by hand every single time, on a
        form that already knows exactly who the customer is. On this database
        that is not an edge case: 7050 of 7527 opportunities have an
        ``email_from`` but no ``partner_id``.

        So fall back to the opportunity's own email. An existing contact with
        that address is reused; only when there is none is one created, which
        is what converting the lead would have done anyway and is the minimum
        needed for the customer to be able to receive an invitation at all.

        Deliberately does NOT write ``partner_id`` back onto the opportunity:
        linking a customer is a CRM decision with pipeline consequences, not a
        side effect of booking a meeting. The email lookup makes the next
        booking find this same contact, so no duplicates accumulate.
        """
        self.ensure_one()
        lead = self.opportunity_id
        if not lead:
            return self.env["res.partner"]
        if lead.partner_id:
            return lead.partner_id
        email = (lead.email_from or "").strip()
        normalized = email_normalize(email)
        if not normalized:
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        existing = Partner.search([("email_normalized", "=", normalized)], limit=1)
        if existing:
            return existing
        partner = Partner.create({
            "name": lead.contact_name or lead.partner_name or email,
            "email": email,
            "phone": lead.phone or False,
        })
        _logger.info(
            "Created contact %s (%s) from opportunity %s so the customer can "
            "be invited to meeting %s",
            partner.id, normalized, lead.id, self.id,
        )
        return partner

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
        # Second layer of the recursion guard: even if resource_booking does
        # lazily spawn its own calendar.event, that event must not turn around
        # and book again. Belt and braces on purpose -- the failure mode is an
        # unbounded create loop that surfaces to the user as a validation error
        # listing the same booking N times.
        if self.env.context.get("sgc_skip_meeting_register"):
            return
        for event in self:
            # Resource booking + AI session stay strictly CRM-scoped: they key
            # off the opportunity and would otherwise spawn bookings/sessions
            # for every externally-attended meeting in the database.
            if not event.opportunity_id:
                continue
            # Invite the customer the meeting is *about*. Booking from an
            # opportunity form and then having to type the customer's name in
            # by hand is the kind of papercut that gets forgotten, and a
            # forgotten attendee means the customer never learns about their
            # own meeting.
            try:
                customer = event._sgc_get_opportunity_attendee()
                if customer and customer not in event.partner_ids:
                    event.with_context(
                        sgc_applying_meet_organizer=True
                    ).partner_ids = [(4, customer.id)]
            except Exception:
                _logger.exception(
                    "Failed to add the opportunity's customer to event %s",
                    event.id,
                )
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
        # A cancelled meeting must take its notetaker with it. Odoo cancels a
        # meeting by archiving it, so active=False is the cancel signal; the
        # bot is scheduled days ahead and would otherwise still walk into the
        # room on the day. Same when the user simply switches the bot off.
        if vals.get("active") is False or vals.get("sgc_bot_enabled") is False:
            self._sgc_sessions().cancel_bot(
                reason=_("the meeting was cancelled")
                if vals.get("active") is False
                else _("the AI notetaker was switched off"),
            )
        self._sgc_register_meeting()
        # An un-archived meeting needs its bot back: _sgc_register_meeting only
        # dispatches when no session exists yet, and the cancel above cleared
        # bot_dispatched, so this hands it to the normal dispatch path.
        if vals.get("active") is True:
            self._sgc_sessions().filtered(
                lambda s: s.bot_enabled and not s.bot_dispatched
            ).action_dispatch_bot()
        # A moved meeting (or one whose Meet room changed) must drag its
        # already-scheduled notetaker along with it, otherwise the bot turns up
        # at the old time in the old room.
        if {"start", "stop", "videocall_location"} & set(vals):
            sessions = self._sgc_sessions().filtered("bot_dispatched")
            if sessions:
                try:
                    sessions._sync_bot_schedule()
                except Exception:
                    _logger.exception(
                        "Failed to re-schedule AI notetaker for events %s", self.ids
                    )
        # A meeting linked to its opportunity after creation reaches the same
        # state a fresh CRM booking does, and would otherwise wait for the 12h
        # cron. The internal writes made by _sgc_register_meeting carry
        # sgc_applying_meet_organizer, so this does not re-enter on those.
        if not self.env.context.get("sgc_applying_meet_organizer"):
            self._sgc_push_to_google()
        return res

    def unlink(self):
        # Deleting the meeting cascades the session away, so the bot has to be
        # called off first or it would join a meeting Odoo no longer knows about.
        self._sgc_sessions().cancel_bot(reason=_("the meeting was deleted"))
        return super().unlink()
