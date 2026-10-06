# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""HTTP controllers for the SGC Meeting AI module.

Exposes:
  - POST /sgc_meeting_ai/webhook/<provider_code>/upload
      Receives meeting recordings from a third-party bot service
      (Recall.ai, custom bot, etc.). The bot POSTs the audio file plus
      metadata. Odoo stores the recording, queues transcription, and
      posts AI notes to the meeting's chatter.

  - GET /sgc_meeting_ai/health
      Liveness check.

  - POST /sgc_meeting_ai/transcript/<session_id>
      Manual transcript upload (paste-text, file upload, etc.).
"""

import base64
import hmac
import json
import logging
import secrets
import time

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SGCMeetingAIController(http.Controller):
    @http.route("/sgc_meeting_ai/health", type="http", auth="public", csrf=False)
    def health(self, **kwargs):
        return request.make_response(
            json.dumps({"status": "ok", "module": "sgc_meeting_ai"}),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/sgc_meeting_ai/webhook/<string:provider_code>/upload",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def webhook_upload(self, provider_code, **kwargs):
        """Receive a recording + metadata from a bot service.

        Expected payload (multipart/form-data):
          - file:           binary audio/video file
          - meeting_id:     Odoo calendar.event id (int)
          - meeting_url:    (optional) external meeting URL
          - duration:       (optional) duration in seconds
          - language:       (optional) ISO 639-1 code
          - bot_id:         (optional) external bot identifier
          - started_at:     (optional) ISO datetime the recording started
          - signature:      (optional) HMAC-SHA256 of the body using
                            provider.webhook_token as key. Required if
                            a token is configured.
        """
        provider = (
            request.env["sgc.meeting.provider"]
            .sudo()
            .search([("code", "=", provider_code)], limit=1)
        )
        if not provider:
            return request.make_response(
                json.dumps({"error": "unknown_provider", "code": provider_code}),
                status=404,
                headers=[("Content-Type", "application/json")],
            )

        # HMAC verification
        if provider.webhook_token:
            provided_sig = request.httprequest.headers.get("X-SGC-Signature") or kwargs.get(
                "signature"
            )
            if not provided_sig:
                return request.make_response(
                    json.dumps({"error": "missing_signature"}),
                    status=401,
                    headers=[("Content-Type", "application/json")],
                )
            raw_body = request.httprequest.get_data() or b""
            expected = hmac.new(
                provider.webhook_token.encode(), raw_body, __import__("hashlib").sha256
            ).hexdigest()
            if not hmac.compare_digest(provided_sig, expected):
                _logger.warning(
                    "Webhook signature mismatch for provider %s", provider_code
                )
                return request.make_response(
                    json.dumps({"error": "bad_signature"}),
                    status=401,
                    headers=[("Content-Type", "application/json")],
                )

        # Validate required fields
        try:
            meeting_id = int(kwargs.get("meeting_id", 0))
        except (TypeError, ValueError):
            meeting_id = 0
        if not meeting_id:
            return request.make_response(
                json.dumps({"error": "missing_meeting_id"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )
        uploaded = request.httprequest.files.get("file")
        if not uploaded:
            return request.make_response(
                json.dumps({"error": "missing_file"}),
                status=400,
                headers=[("Content-Type", "application/json")],
            )

        meeting = (
            request.env["calendar.event"].sudo().browse(meeting_id).exists()
        )
        if not meeting:
            return request.make_response(
                json.dumps({"error": "meeting_not_found", "id": meeting_id}),
                status=404,
                headers=[("Content-Type", "application/json")],
            )

        # Get or create the SGC session
        session = meeting.sgc_session_id
        if not session:
            session = (
                request.env["sgc.meeting.session"]
                .sudo()
                .create(
                    {
                        "meeting_id": meeting.id,
                        "provider_id": provider.id,
                        "state": "recording_uploaded",
                        "bot_id": kwargs.get("bot_id"),
                    }
                )
            )
        else:
            session.write({"provider_id": provider.id, "state": "recording_uploaded"})

        # Store the audio as ir.attachment
        file_content = uploaded.read()
        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": uploaded.filename or "meeting_recording",
                    "datas": base64.b64encode(file_content),
                    "res_model": "sgc.meeting.recording",
                    "mimetype": uploaded.mimetype or "application/octet-stream",
                    "public": False,
                }
            )
        )

        # Create the recording record
        recording = (
            request.env["sgc.meeting.recording"]
            .sudo()
            .create(
                {
                    "session_id": session.id,
                    "attachment_id": attachment.id,
                    "duration_seconds": int(kwargs.get("duration") or 0),
                    "language": kwargs.get("language") or "en",
                }
            )
        )

        _logger.info(
            "Webhook received recording %s for meeting %s (provider=%s, size=%d)",
            recording.id,
            meeting_id,
            provider_code,
            len(file_content),
        )

        # Kick off the AI pipeline asynchronously if a queue job is available;
        # otherwise process inline (still fast for typical recordings).
        try:
            recording.action_transcribe()
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Inline transcription failed for recording %s", recording.id)
            return request.make_response(
                json.dumps(
                    {
                        "ok": True,
                        "recording_id": recording.id,
                        "session_id": session.id,
                        "transcription_error": str(exc)[:300],
                    }
                ),
                status=202,
                headers=[("Content-Type", "application/json")],
            )

        # After transcription, summarize automatically
        try:
            if session.transcript_id:
                session.transcript_id.action_generate_notes()
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Inline summarization failed for session %s", session.id)
            return request.make_response(
                json.dumps(
                    {
                        "ok": True,
                        "recording_id": recording.id,
                        "session_id": session.id,
                        "transcript_id": session.transcript_id.id,
                        "summarization_error": str(exc)[:300],
                    }
                ),
                status=200,
                headers=[("Content-Type", "application/json")],
            )

        return request.make_response(
            json.dumps(
                {
                    "ok": True,
                    "recording_id": recording.id,
                    "session_id": session.id,
                    "transcript_id": session.transcript_id.id if session.transcript_id else None,
                    "notes_id": session.notes_id.id if session.notes_id else None,
                    "state": session.state,
                }
            ),
            headers=[("Content-Type", "application/json")],
        )

    @http.route(
        "/sgc_meeting_ai/transcript/<int:session_id>",
        type="http",
        auth="user",
        methods=["POST", "GET"],
        csrf=False,
    )
    def upload_transcript(self, session_id, **kwargs):
        """Manual transcript upload form (paste text or upload txt/vtt)."""
        session = request.env["sgc.meeting.session"].browse(session_id)
        if not session.exists():
            return request.make_response("Session not found", status=404)

        if request.httprequest.method == "GET":
            return request.render(
                "sgc_meeting_ai.upload_transcript_form",
                {"session": session, "csrf_token": request.csrf_token()},
            )

        text = kwargs.get("transcript_text", "").strip()
        if not text and "file" in request.httprequest.files:
            uploaded = request.httprequest.files["file"]
            text = uploaded.read().decode("utf-8", errors="replace").strip()
        if not text:
            return request.make_response("No transcript provided", status=400)

        transcript = request.env["sgc.meeting.transcript"].create(
            {
                "session_id": session.id,
                "text": text,
                "language": kwargs.get("language") or "en",
                "model": "manual_upload",
            }
        )
        session.write({"transcript_id": transcript.id, "state": "transcribed"})
        transcript.action_generate_notes()
        return request.redirect(f"/web#id={session.meeting_id.id}&model=calendar.event&view_type=form")
