# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import re

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class SGCMeetingTranscript(models.Model):
    """Full transcript of a meeting recording.

    Produced by the Whisper transcription service. Acts as the source
    for downstream LLM summarization.
    """

    _name = "sgc.meeting.transcript"
    _description = "SGC Meeting Transcript"
    _inherit = ["mail.thread"]
    _order = "create_date desc"
    _rec_name = "display_name"

    display_name = fields.Char(compute="_compute_display_name", store=True)
    session_id = fields.Many2one(
        "sgc.meeting.session", required=True, ondelete="cascade", index=True
    )
    recording_id = fields.Many2one(
        "sgc.meeting.recording",
        string="Recording",
        ondelete="set null",
    )
    text = fields.Text(required=True)
    language = fields.Char(string="Language Code")
    model = fields.Char(string="Whisper Model")
    duration_seconds = fields.Integer()
    word_count = fields.Integer(compute="_compute_word_count", store=True)
    char_count = fields.Integer(compute="_compute_word_count", store=True)
    notes_id = fields.Many2one(
        "sgc.meeting.notes",
        string="AI Notes",
        readonly=True,
    )

    @api.depends("text", "session_id")
    def _compute_display_name(self):
        for tr in self:
            base = tr.session_id.name or _("Transcript")
            stamp = tr.create_date.strftime("%Y-%m-%d %H:%M") if tr.create_date else ""
            tr.display_name = f"{base} — {stamp}" if stamp else base

    @api.depends("text")
    def _compute_word_count(self):
        for tr in self:
            text = tr.text or ""
            tr.char_count = len(text)
            tr.word_count = len(re.findall(r"\b\w+\b", text))

    def action_generate_notes(self):
        """Trigger LLM summarization on this transcript."""
        self.ensure_one()
        service = self.env["sgc.meeting.notes.service"]
        return service.summarize(self)
