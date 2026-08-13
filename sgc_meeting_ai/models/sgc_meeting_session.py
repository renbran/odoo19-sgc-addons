# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging
import mimetypes
import os
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.attendee_service import PLACEHOLDER_PREFIX

_logger = logging.getLogger(__name__)


class SGCMeetingSession(models.Model):
    """A meeting session tracked by SGC Meeting AI.

    Linked 1:1 to a calendar.event (and indirectly to a resource.booking).
    Holds references to recordings, transcripts, and AI-generated notes.
    """

    _name = "sgc.meeting.session"
    _description = "SGC Meeting Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        compute="_compute_name", store=True, readonly=False, index=True
    )
    meeting_id = fields.Many2one(
        "calendar.event",
        string="Calendar Event",
        required=True,
        ondelete="cascade",
        index=True,
    )

    provider_id = fields.Many2one(
        "sgc.meeting.provider",
        string="Provider",
        required=True,
        index=True,
    )
    start = fields.Datetime(related="meeting_id.start", store=True, index=True)
    stop = fields.Datetime(related="meeting_id.stop", store=True)
    duration_minutes = fields.Integer(
        compute="_compute_duration", store=True, string="Duration (min)"
    )
    attendee_ids = fields.Many2many(
        "res.partner",
        related="meeting_id.partner_ids",
        string="Attendees",
    )
    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("recording_uploaded", "Recording Uploaded"),
            ("transcribing", "Transcribing"),
            ("transcribed", "Transcribed"),
            ("summarizing", "Summarizing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="scheduled",
        required=True,
        index=True,
    )
    state_message = fields.Char(help="Last error or status message")
    recording_ids = fields.One2many(
        "sgc.meeting.recording",
        "session_id",
        string="Recordings",
    )
    recording_count = fields.Integer(
        compute="_compute_recording_count", string="Recording Count"
    )
    transcript_id = fields.Many2one(
        "sgc.meeting.transcript",
        string="Transcript",
        readonly=True,
    )
    notes_id = fields.Many2one(
        "sgc.meeting.notes",
        string="AI Notes",
        readonly=True,
    )
    bot_enabled = fields.Boolean(
        string="AI Bot Auto-Join",
        default=False,
        help="If True, the configured bot service will be requested to auto-join this meeting.",
    )
    bot_dispatched = fields.Boolean(
        string="Bot Dispatched",
        readonly=True,
    )
    bot_id = fields.Char(string="External Bot ID", readonly=True)
    bot_state = fields.Char(
        string="Bot State",
        readonly=True,
        help="Last known state of the external meeting bot (Attendee).",
    )
    bot_join_at = fields.Datetime(
        string="Bot Joins At",
        readonly=True,
        help="When the external bot is scheduled to enter the meeting. "
        "Set from the meeting start time, not the booking time.",
    )
    video_url = fields.Char(
        related="meeting_id.videocall_location", string="Meeting Link"
    )

    _sql_constraints = [
        (
            "meeting_id_unique",
            "UNIQUE(meeting_id)",
            "Only one SGC session per calendar event allowed.",
        ),
    ]

    @api.depends("recording_ids")
    def _compute_recording_count(self):
        for session in self:
            session.recording_count = len(session.recording_ids)

    @api.depends("meeting_id.name", "start")
    def _compute_name(self):
        for session in self:
            base = session.meeting_id.name or session.meeting_id.display_name
            if session.start:
                session.name = f"{base} — {session.start.strftime('%Y-%m-%d %H:%M')}"
            else:
                session.name = base or _("New Meeting Session")

    @api.depends("start", "stop")
    def _compute_duration(self):
        for session in self:
            if session.start and session.stop:
                delta = session.stop - session.start
                session.duration_minutes = int(delta.total_seconds() / 60)
            else:
                session.duration_minutes = 0

    def action_dispatch_bot(self):
        """Schedule an AI notetaker bot for the meeting.

        Uses the Attendee service (open-source, self-hostable, free). The bot
        is scheduled against the meeting's own start time, not dispatched on
        the spot: a session is created when the meeting is *booked*, which is
        usually days before it happens.

        A session that cannot be dispatched yet (no API key, or the Google Meet
        link has not synced back from Google yet) is deliberately left with
        ``bot_dispatched = False`` so ``_cron_dispatch_due_bots`` retries it.
        """
        attendee = self.env["sgc.meeting.attendee.service"]
        configured = attendee.is_configured()
        for session in self:
            if not session.bot_enabled:
                session.bot_enabled = True
            if configured and session.video_url:
                session._dispatch_bot_now(attendee)
                continue
            # Not dispatchable yet. Record why, but do NOT set bot_dispatched:
            # that flag is the "a bot is on its way" latch, and setting it here
            # is what silently retired every session that was booked before its
            # Meet link existed.
            reason = (
                _("the meeting link has not synced from Google yet")
                if configured
                else _("no bot provider is configured "
                       "(set sgc_meeting_ai.attendee_api_key)")
            )
            message = _("Waiting to dispatch AI notetaker: %s.", reason)
            # Only speak up when something actually changed — this runs on
            # every write to the meeting and would otherwise flood the log.
            if session.state_message != message:
                session.sudo().write({"state_message": message[:250]})
                session.message_post(body=message)
        return True

    def _dispatch_bot_now(self, attendee=None):
        """Create the Attendee bot for this session. Assumes a link exists."""
        self.ensure_one()
        attendee = attendee or self.env["sgc.meeting.attendee.service"]
        try:
            self._invite_bot_to_meeting()
            bot = attendee.create_bot(self)
        except Exception as exc:  # noqa: BLE001
            # A rejected deduplication key means the bot we wanted is already
            # live over at Attendee and only Odoo lost track of it. Adopt it,
            # otherwise the cron retries this session every 5 minutes forever.
            bot = attendee.find_bot_by_dedup_key(f"odoo-session-{self.id}")
            if not bot:
                _logger.exception(
                    "Attendee bot dispatch failed for session %s", self.id
                )
                # Left undispatched on purpose so the cron picks it up again:
                # most failures here are transient (network, 5xx, rate limit).
                message = _("Could not schedule the AI notetaker: %s", str(exc))
                if self.state_message != message:
                    self.message_post(body=message)
                self.sudo().write({"state_message": message[:250]})
                return False
            _logger.info(
                "Adopted existing Attendee bot %s for session %s",
                bot.get("id"), self.id,
            )
        # Trust the bot's own join_at when Attendee reports one (it is
        # authoritative, and on the adopt path it may differ from ours).
        join_at = attendee.parse_join_at(bot) or attendee.compute_join_at(self)
        self.sudo().write({
            "bot_dispatched": True,
            "bot_id": bot.get("id"),
            "bot_state": bot.get("state"),
            "bot_join_at": join_at or False,
            "state_message": False,
        })
        self.message_post(
            body=_(
                "AI notetaker scheduled via Attendee (bot %(bot)s). It will "
                "join at %(when)s UTC, then record and transcribe "
                "automatically.",
                bot=bot.get("id"),
                when=fields.Datetime.to_string(join_at) if join_at
                else _("the start of the meeting"),
            )
        )
        return True

    def cancel_bot(self, reason=None):
        """Call off the notetaker for these sessions.

        Safe to call on sessions that never had a bot. Clears the dispatch
        latch so the session can be re-armed if the meeting comes back.
        """
        attendee = self.env["sgc.meeting.attendee.service"]
        for session in self:
            if not session.bot_id or session.bot_id.startswith(PLACEHOLDER_PREFIX):
                # Nothing live at Attendee, but still drop the latch so an
                # un-cancelled meeting re-arms cleanly.
                session.sudo().write({"bot_dispatched": False, "bot_id": False,
                                      "bot_join_at": False})
                continue
            cancelled = False
            if attendee.is_configured():
                try:
                    cancelled = attendee.delete_bot(session.bot_id)
                except Exception:
                    _logger.exception(
                        "Failed to cancel Attendee bot %s for session %s",
                        session.bot_id, session.id,
                    )
            body = (
                _("AI notetaker cancelled: %s.", reason)
                if reason
                else _("AI notetaker cancelled.")
            )
            if not cancelled:
                body += _(
                    " Attendee would not call the bot back — it may have "
                    "already joined or already finished."
                )
            session.message_post(body=body)
            session.sudo().write({
                "bot_dispatched": False,
                "bot_id": False,
                "bot_join_at": False,
                "bot_state": False,
            })
        return True

    def action_cancel_bot(self):
        return self.cancel_bot(reason=_("cancelled from the session"))

    def _sync_bot_schedule(self):
        """Keep an already-scheduled bot aligned with the meeting.

        A meeting that gets moved after the bot was scheduled would otherwise
        keep the bot pointed at the old time (or the old room).
        """
        attendee = self.env["sgc.meeting.attendee.service"]
        if not attendee.is_configured():
            return
        for session in self:
            if not session.bot_dispatched or not session.bot_id:
                continue
            if session.bot_id.startswith(PLACEHOLDER_PREFIX):
                continue
            join_at = attendee.compute_join_at(session)
            if not join_at:
                continue
            payload = {"join_at": attendee._to_iso_utc(join_at)}
            if session.video_url:
                payload["meeting_url"] = session.video_url
            try:
                attendee.update_bot(session.bot_id, payload)
            except Exception:
                # Attendee refuses the PATCH once the bot has left "scheduled".
                # Nothing to do then — the bot is already in the room.
                _logger.info(
                    "Could not re-schedule Attendee bot %s for session %s "
                    "(likely no longer in the scheduled state)",
                    session.bot_id, session.id,
                )
                continue
            session.sudo().write({"bot_join_at": join_at})

    def _cron_dispatch_due_bots(self):
        """Dispatch bots for meetings that could not be dispatched at booking.

        Covers the normal CRM flow: the session is created the moment the
        meeting is booked, but its Google Meet link only appears minutes later
        when google_calendar syncs the event back. Without this the bot is
        never scheduled at all.
        """
        attendee = self.env["sgc.meeting.attendee.service"]
        if not attendee.is_configured():
            return
        now = fields.Datetime.now()
        sessions = self.search([
            ("bot_enabled", "=", True),
            ("state", "=", "scheduled"),
            # Don't chase meetings that already finished.
            ("stop", ">", now - timedelta(minutes=5)),
            # ...or ones booked absurdly far out; they get picked up later.
            ("start", "<", now + timedelta(days=30)),
            "|",
            ("bot_dispatched", "=", False),
            ("bot_id", "=like", f"{PLACEHOLDER_PREFIX}%"),
        ])
        for session in sessions:
            if not session.video_url:
                continue
            try:
                # Self-heal sessions retired by the old placeholder behaviour.
                if session.bot_id and session.bot_id.startswith(PLACEHOLDER_PREFIX):
                    session.sudo().write({"bot_id": False, "bot_dispatched": False})
                session._dispatch_bot_now(attendee)
            except Exception:
                _logger.exception(
                    "Attendee bot dispatch cron failed for session %s", session.id
                )

    def _invite_bot_to_meeting(self):
        """Add the bot's Google account as a meeting attendee.

        On free Google Meet the host must admit outside participants; inviting
        the bot's account up front means it is auto-admitted instead of stuck in
        the waiting room. No-op if no bot email is configured.
        """
        self.ensure_one()
        email = self.env["ir.config_parameter"].sudo().get_param(
            "sgc_meeting_ai.attendee_bot_email"
        )
        if not email or not self.meeting_id:
            return
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("email", "=ilike", email)], limit=1)
        if not partner:
            partner = Partner.create({"name": "SGC AI Notetaker", "email": email})
        if partner not in self.meeting_id.partner_ids:
            self.meeting_id.sudo().write({"partner_ids": [(4, partner.id)]})

    def _cron_poll_attendee_bots(self):
        """Poll dispatched Attendee bots and ingest finished meetings."""
        attendee = self.env["sgc.meeting.attendee.service"]
        if not attendee.is_configured():
            return
        sessions = self.search([
            ("bot_dispatched", "=", True),
            ("bot_id", "!=", False),
            ("bot_id", "not like", PLACEHOLDER_PREFIX),
            ("state", "in", ["scheduled", "in_progress"]),
        ])
        for session in sessions:
            if not session.bot_id or session.bot_id.startswith(PLACEHOLDER_PREFIX):
                continue
            try:
                attendee.ingest(session)
            except Exception:
                _logger.exception(
                    "Attendee poll/ingest failed for session %s", session.id
                )

    def action_process_recording(self):
        """Trigger AI pipeline for the latest uploaded recording.

        Pipeline: recording -> Whisper transcription -> LLM notes.
        """
        self.ensure_one()
        if not self.recording_ids:
            raise UserError(_("Upload a recording first."))
        recording = self.recording_ids[0]
        if recording.state != "uploaded":
            raise UserError(
                _(f"Recording is in state {recording.state}, cannot process.")
            )
        recording.action_transcribe()
        return True

    def _cron_process_pending_sessions(self):
        """Cron entry: process sessions that have recordings ready."""
        sessions = self.search(
            [
                ("state", "in", ["recording_uploaded", "transcribing", "transcribed"]),
            ]
        )
        for session in sessions:
            try:
                if session.state == "recording_uploaded":
                    session.action_process_recording()
            except Exception as exc:
                _logger.exception("Failed to process session %s", session.id)
                session.write(
                    {
                        "state": "failed",
                        "state_message": str(exc)[:250],
                    }
                )
