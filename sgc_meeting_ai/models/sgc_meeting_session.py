# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging
import mimetypes
import os
import secrets
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

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
        """Send an AI notetaker bot into the meeting.

        Uses the Attendee service (open-source, self-hostable, free) when it is
        configured. If Attendee is not configured or the meeting has no video
        link, we fall back to recording the intent so nothing breaks.
        """
        attendee = self.env["sgc.meeting.attendee.service"]
        configured = attendee.is_configured()
        for session in self:
            if not session.bot_enabled:
                session.bot_enabled = True
            meeting_url = session.video_url
            if configured and meeting_url:
                try:
                    session._invite_bot_to_meeting()
                    bot = attendee.create_bot(session)
                    session.write({
                        "bot_dispatched": True,
                        "bot_id": bot.get("id"),
                        "bot_state": bot.get("state"),
                        "state": "in_progress",
                        "state_message": False,
                    })
                    session.message_post(
                        body=_(
                            "AI notetaker bot dispatched to the meeting via "
                            "Attendee (bot %s). It will join, record "
                            "and transcribe automatically.",
                            bot.get("id"),
                        )
                    )
                    continue
                except Exception as exc:  # noqa: BLE001
                    _logger.exception(
                        "Attendee bot dispatch failed for session %s", session.id
                    )
                    session.write({
                        "bot_dispatched": True,
                        "state_message": f"Attendee dispatch failed: {exc}"[:250],
                    })
                    session.message_post(
                        body=_(
                            "Could not dispatch the AI bot via Attendee: "
                            "%s",
                            str(exc),
                        )
                    )
                    continue
            # Fallback: record intent (Attendee not configured or no link yet).
            session.bot_dispatched = True
            session.bot_id = f"sgc-pending-{secrets.token_hex(4)}"
            reason = (
                _("no meeting link is set yet")
                if configured
                else _("no bot provider is configured")
            )
            session.message_post(
                body=_(
                    "AI bot dispatch requested, but %s. Set "
                    "sgc_meeting_ai.attendee_api_key (and a meeting "
                    "link) so the bot can auto-join, record and transcribe.",
                    reason,
                )
            )
        return True

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
            ("state", "in", ["scheduled", "in_progress"]),
        ])
        for session in sessions:
            if not session.bot_id or session.bot_id.startswith("sgc-pending-"):
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
