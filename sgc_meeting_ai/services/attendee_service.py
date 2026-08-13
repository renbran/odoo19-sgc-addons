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
from datetime import datetime, timedelta, timezone

import requests

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

# Attendee bot states that mean the meeting is over and post-processing is done.
# These mirror Attendee's own BotStates.post_meeting_states().
_TERMINAL_OK_STATES = {"ended"}
_TERMINAL_FAIL_STATES = {"fatal_error", "data_deleted"}

# Attendee's BotStates.pre_meeting_states(): the bot is queued but has not yet
# tried to enter the room. A bot sitting in these is healthy, not stuck — it is
# waiting for its scheduled join_at.
PRE_MEETING_STATES = {"scheduled", "ready", "staged"}

# Placeholder bot ids written by older versions of this module when Attendee
# was not configured (or the meeting link had not synced yet). They are not
# real bot ids: the poller must ignore them and the dispatcher must treat the
# session as still needing a bot.
PLACEHOLDER_PREFIX = "sgc-pending-"


class SGCMeetingAttendeeService(models.AbstractModel):
    _name = "sgc.meeting.attendee.service"
    _description = "SGC Meeting Attendee Bot Service"

    DEFAULT_BASE_URL = "https://app.attendee.dev"
    DEFAULT_BOT_NAME = "SGC AI Notetaker"
    HTTP_TIMEOUT = 30
    DOWNLOAD_TIMEOUT = 180

    # Attendee rejects a join_at in the past and needs a moment to allocate the
    # bot, so a join_at that is due (or nearly due) is pushed this far out.
    MIN_LEAD_SECONDS = 180
    # How early the bot should be in the room. Joining exactly on the hour
    # means missing the first exchange while it negotiates admission.
    JOIN_EARLY_SECONDS = 60

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
    def compute_join_at(self, session):
        """Return the UTC datetime the bot should join, or None for 'now'.

        Attendee joins immediately when no ``join_at`` is given. Sessions are
        created when the meeting is *booked*, which is routinely days ahead of
        the meeting itself, so omitting ``join_at`` sends the bot into an empty
        room where nobody is present to admit it — it waits out its timeout and
        dies with ``request_to_join_denied``. Always schedule against the
        meeting's own start time.
        """
        start = session.start
        if not start:
            return None
        join_at = start - timedelta(seconds=self.JOIN_EARLY_SECONDS)
        floor = fields.Datetime.now() + timedelta(seconds=self.MIN_LEAD_SECONDS)
        # A meeting starting now (or already running) still gets a bot, just
        # far enough out that Attendee accepts it.
        return max(join_at, floor)

    @staticmethod
    def _to_iso_utc(value):
        # Odoo stores naive UTC datetimes; Attendee wants ISO 8601 with a zone.
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def parse_join_at(bot):
        """Read a bot payload's join_at back into a naive UTC datetime."""
        raw = (bot or {}).get("join_at")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

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
            # Attendee refuses a second bot with the same key while one is
            # still live, so a double dispatch cannot put two notetakers in
            # the same room.
            "deduplication_key": f"odoo-session-{session.id}",
        }
        join_at = self.compute_join_at(session)
        if join_at:
            payload["join_at"] = self._to_iso_utc(join_at)
        return self._request("POST", "/api/v1/bots", cfg=cfg, json=payload)

    def find_bot_by_dedup_key(self, key):
        """Return the live bot carrying this deduplication key, if any.

        Attendee rejects a second bot with a key that is already in use by a
        non-terminal bot. That rejection means "the bot you wanted already
        exists" — so we adopt it rather than retrying forever.
        """
        try:
            data = self._request(
                "GET", "/api/v1/bots", params={"deduplication_key": key}
            )
        except requests.RequestException:
            return None
        results = data.get("results") if isinstance(data, dict) else data
        for bot in results or []:
            if bot.get("deduplication_key") == key:
                return bot
        return None

    def update_bot(self, bot_id, payload):
        """PATCH a bot. Attendee only accepts join_at / meeting_url changes
        while the bot is still in the ``scheduled`` state."""
        return self._request("PATCH", f"/api/v1/bots/{bot_id}", json=payload)

    def delete_bot(self, bot_id):
        """Cancel a scheduled bot so it never joins. Returns True if gone.

        Attendee only allows deleting a bot that has not started yet. Once it
        is in the room, ``leave`` is the way out — deleting is refused, and
        that refusal is not an error worth surfacing.
        """
        try:
            self._request("DELETE", f"/api/v1/bots/{bot_id}")
            return True
        except requests.RequestException:
            pass
        try:
            self._request("POST", f"/api/v1/bots/{bot_id}/leave")
            return True
        except requests.RequestException:
            _logger.info(
                "Attendee bot %s could not be cancelled (already terminal?)",
                bot_id,
            )
            return False

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
            # Still queued / joining / recording / post-processing. Once the bot
            # stops merely waiting for its join_at, reflect that in the session
            # so the pipeline status means something before the meeting ends.
            if state and state not in PRE_MEETING_STATES and session.state == "scheduled":
                session.sudo().write({"state": "in_progress"})
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
