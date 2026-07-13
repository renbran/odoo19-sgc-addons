# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Attendee meeting-bot service.

Attendee (https://github.com/attendee-labs/attendee) is an open-source,
self-hostable "universal meeting bot API" — a free alternative to Recall.ai.
It sends a bot into a Google Meet / Zoom call, records it, and transcribes it
(via Deepgram). We use its REST API to:

  1. dispatch a bot into a meeting          (POST /api/v1/bots)
  2. poll the bot until the meeting ends     (GET  /api/v1/bots/<id>)
  3. ingest the transcript and recording     (GET  /api/v1/bots/<id>/transcript
                                              GET  /api/v1/bots/<id>/recording)

Because Attendee already transcribes the meeting, we ingest its transcript
directly and run the existing LLM-notes step — no Whisper key required.

Configuration (Settings -> Technical -> System Parameters):
  - sgc_meeting_ai.attendee_base_url   (default https://app.attendee.dev)
  - sgc_meeting_ai.attendee_api_key    (required to enable dispatch)
  - sgc_meeting_ai.attendee_bot_name   (default "SGC AI Notetaker")
"""

import base64
import logging

import requests

from odoo import _, models

_logger = logging.getLogger(__name__)

# Attendee bot states that mean the meeting is over and post-processing is done.
_TERMINAL_OK_STATES = {"ended"}
_TERMINAL_FAIL_STATES = {"fatal_error"}

# Placeholder bot ids written when Attendee is not configured; the poller
# must ignore these.
PLACEHOLDER_PREFIX = "sgc-pending-"


class SGCMeetingAttendeeService(models.AbstractModel):
    _name = "sgc.meeting.attendee.service"
    _description = "SGC Meeting Attendee Bot Service"

    DEFAULT_BASE_URL = "https://app.attendee.dev"
    DEFAULT_BOT_NAME = "SGC AI Notetaker"
    HTTP_TIMEOUT = 30
    DOWNLOAD_TIMEOUT = 180

    # ------------------------------------------------------------------
    # Config / HTTP helpers
    # ------------------------------------------------------------------
    def _get_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        base = (
            ICP.get_param("sgc_meeting_ai.attendee_base_url")
            or self.DEFAULT_BASE_URL
        ).rstrip("/")
        return {
            "base_url": base,
            "api_key": ICP.get_param("sgc_meeting_ai.attendee_api_key") or "",
            "bot_name": ICP.get_param("sgc_meeting_ai.attendee_bot_name")
            or self.DEFAULT_BOT_NAME,
        }

    def is_configured(self):
        return bool(self._get_config()["api_key"])

    def _headers(self, cfg):
        return {
            "Authorization": f"Token {cfg['api_key']}",
            "Content-Type": "application/json",
        }

    def _request(self, method, path, cfg=None, **kwargs):
        cfg = cfg or self._get_config()
        url = f"{cfg['base_url']}{path}"
        kwargs.setdefault("timeout", self.HTTP_TIMEOUT)
        resp = requests.request(method, url, headers=self._headers(cfg), **kwargs)
        resp.raise_for_status()
        if resp.content:
            try:
                return resp.json()
            except ValueError:
                return {}
        return {}

    # ------------------------------------------------------------------
    # API operations
    # ------------------------------------------------------------------
    def create_bot(self, session):
        """Dispatch a bot into the session's meeting. Returns the bot dict."""
        cfg = self._get_config()
        meeting_url = session.video_url or session.meeting_id.videocall_location
        if not meeting_url:
            raise ValueError("Meeting has no video call link to send a bot to.")
        payload = {
            "meeting_url": meeting_url,
            "bot_name": cfg["bot_name"],
            # Echoed back by Attendee; lets us correlate webhooks if enabled.
            "metadata": {
                "odoo_meeting_id": str(session.meeting_id.id),
                "odoo_session_id": str(session.id),
            },
        }
        return self._request("POST", "/api/v1/bots", cfg=cfg, json=payload)

    def get_bot(self, bot_id):
        return self._request("GET", f"/api/v1/bots/{bot_id}")

    def get_transcript(self, bot_id):
        """Return the transcript as a list of utterance dicts."""
        data = self._request("GET", f"/api/v1/bots/{bot_id}/transcript")
        if isinstance(data, dict):
            return data.get("results") or data.get("transcript") or []
        return data or []

    def get_recording_url(self, bot_id):
        """Best-effort: return a downloadable recording URL, or None."""
        try:
            data = self._request("GET", f"/api/v1/bots/{bot_id}/recording")
        except requests.RequestException:
            return None
        if isinstance(data, list):
            data = data[0] if data else {}
        if isinstance(data, dict):
            return (
                data.get("url")
                or data.get("recording_url")
                or data.get("download_url")
            )
        return None

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    @staticmethod
    def _format_transcript(utterances):
        lines = []
        for utt in utterances:
            speaker = utt.get("speaker_name") or "Speaker"
            text = utt.get("transcription")
            if isinstance(text, dict):
                text = text.get("transcript") or text.get("text") or ""
            text = (text or "").strip()
            if text:
                lines.append(f"{speaker}: {text}")
        return "\n".join(lines)

    def _store_recording(self, session, bot_id):
        """Download the Attendee recording and store it. Returns recording or None."""
        url = self.get_recording_url(bot_id)
        if not url:
            return None
        try:
            resp = requests.get(url, timeout=self.DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            content = resp.content
        except requests.RequestException as exc:
            _logger.warning(
                "Could not download Attendee recording for bot %s: %s", bot_id, exc
            )
            return None
        attachment = self.env["ir.attachment"].sudo().create({
            "name": f"meeting_{session.meeting_id.id}_recording.mp4",
            "datas": base64.b64encode(content),
            "res_model": "sgc.meeting.recording",
            "mimetype": "video/mp4",
            "public": False,
        })
        # Left in the default "uploaded" state so the Whisper fallback in
        # ingest() can transcribe it if Attendee's own transcript is missing.
        return self.env["sgc.meeting.recording"].sudo().create({
            "session_id": session.id,
            "attachment_id": attachment.id,
        })

    def ingest(self, session):
        """Pull results for a finished bot and run the notes pipeline.

        Returns True if the session was finalized, False if not ready yet.
        """
        bot_id = session.bot_id
        if not bot_id or bot_id.startswith(PLACEHOLDER_PREFIX):
            return False
        data = self.get_bot(bot_id)
        state = (data or {}).get("state")
        session.sudo().write({"bot_state": state or session.bot_state})

        if state in _TERMINAL_FAIL_STATES:
            session.sudo().write({
                "state": "failed",
                "state_message": f"Attendee bot failed (state={state})"[:250],
            })
            return True
        if state not in _TERMINAL_OK_STATES:
            # Still joining / recording / post-processing — check again later.
            return False

        utterances = self.get_transcript(bot_id)
        text = self._format_transcript(utterances)
        recording = self._store_recording(session, bot_id)

        # Primary path: use Attendee's own (Deepgram) transcript.
        if text:
            transcript = self.env["sgc.meeting.transcript"].sudo().create({
                "session_id": session.id,
                "recording_id": recording.id if recording else False,
                "text": text,
                "language": "en",
                "model": "attendee/deepgram",
            })
            if recording:
                recording.sudo().write({
                    "transcript_id": transcript.id,
                    "state": "transcribed",
                    "transcription_model": "attendee/deepgram",
                })
            session.sudo().write({
                "transcript_id": transcript.id,
                "state": "transcribed",
            })
            session.message_post(
                body=_(
                    "AI notetaker finished: transcript ingested from Attendee "
                    "(%d chars). Generating notes…",
                    len(text),
                )
            )
            self._generate_notes(session, transcript)
            return True

        # Fallback: no Attendee transcript, but we have the audio — run the
        # in-module Whisper pipeline on the downloaded recording.
        if recording:
            session.message_post(
                body=_(
                    "Attendee returned no transcript; falling back to Whisper "
                    "on the recording."
                )
            )
            try:
                recording.action_transcribe()
            except Exception:
                _logger.exception(
                    "Whisper fallback failed for session %s (recording %s)",
                    session.id, recording.id,
                )
                return True
            if session.transcript_id:
                self._generate_notes(session, session.transcript_id)
            return True

        # Nothing usable came back from Attendee.
        session.sudo().write({
            "state": "failed",
            "state_message": "Attendee returned no transcript and no recording.",
        })
        return True

    def _generate_notes(self, session, transcript):
        try:
            transcript.action_generate_notes()
        except Exception:
            _logger.exception(
                "Notes generation failed for session %s", session.id
            )
