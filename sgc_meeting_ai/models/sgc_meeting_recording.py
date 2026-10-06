# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import logging
import os
import tempfile
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SGCMeetingRecording(models.Model):
    """A meeting recording (audio/video file) uploaded to SGC Meeting AI.

    Audio is transcribed via the configured Whisper provider (Groq, OpenAI,
    or local). The resulting text is stored on a linked transcript record.
    """

    _name = "sgc.meeting.recording"
    _description = "SGC Meeting Recording"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    session_id = fields.Many2one(
        "sgc.meeting.session",
        string="Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    provider_id = fields.Many2one(
        related="session_id.provider_id", string="Provider", store=True
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Audio File",
        ondelete="restrict",
        required=True,
    )
    filename = fields.Char(related="attachment_id.name", readonly=True)
    mimetype = fields.Char(related="attachment_id.mimetype", readonly=True)
    file_size = fields.Integer(related="attachment_id.file_size", readonly=True)
    duration_seconds = fields.Integer(string="Duration (seconds)")
    language = fields.Char(
        string="Language",
        default="en",
        help="ISO 639-1 code (e.g. 'en', 'es'). Leave 'auto' for detection.",
    )
    state = fields.Selection(
        [
            ("uploaded", "Uploaded"),
            ("transcribing", "Transcribing"),
            ("transcribed", "Transcribed"),
            ("failed", "Failed"),
        ],
        default="uploaded",
        required=True,
        index=True,
    )
    state_message = fields.Char(help="Last error or status message")
    transcription_model = fields.Char(
        string="Whisper Model",
        help="Whisper model used (whisper-large-v3, etc.)",
    )
    transcript_id = fields.Many2one(
        "sgc.meeting.transcript",
        string="Transcript",
        readonly=True,
    )
    uploaded_at = fields.Datetime(default=fields.Datetime.now)

    @api.depends("filename", "session_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.filename or _("Recording")

    @api.constrains("mimetype")
    def _check_audio_mimetype(self):
        audio_prefixes = ("audio/", "video/")
        for rec in self:
            if rec.mimetype and not rec.mimetype.startswith(audio_prefixes):
                raise ValidationError(
                    _(
                        "Only audio/video files are supported. "
                        "Got: %s",
                        rec.mimetype,
                    )
                )

    def action_transcribe(self):
        """Run Whisper transcription via the configured provider service."""
        self.ensure_one()
        if self.state != "uploaded":
            return
        service = self.env["sgc.meeting.transcription.service"]
        try:
            self.write({"state": "transcribing", "state_message": False})
            self.env.cr.commit()
            result = service.transcribe(self)
            transcript = self.env["sgc.meeting.transcript"].create(
                {
                    "session_id": self.session_id.id,
                    "recording_id": self.id,
                    "text": result.get("text", ""),
                    "language": result.get("language", self.language),
                    "model": result.get("model", self.transcription_model or "whisper"),
                    "duration_seconds": result.get("duration", self.duration_seconds),
                }
            )
            self.write(
                {
                    "transcript_id": transcript.id,
                    "state": "transcribed",
                    "transcription_model": result.get("model", False),
                    "language": result.get("language", self.language),
                }
            )
            self.session_id.write(
                {
                    "transcript_id": transcript.id,
                    "state": "transcribed",
                }
            )
            self.session_id.message_post(
                body=_(
                    "<p>Transcription complete (%d chars, lang=%s).</p>",
                    len(result.get("text", "")),
                    result.get("language", "auto"),
                )
            )
        except Exception as exc:
            _logger.exception("Transcription failed for recording %s", self.id)
            self.write(
                {
                    "state": "failed",
                    "state_message": str(exc)[:250],
                }
            )
            self.session_id.write(
                {
                    "state": "failed",
                    "state_message": f"Transcription failed: {exc}"[:250],
                }
            )
            raise
