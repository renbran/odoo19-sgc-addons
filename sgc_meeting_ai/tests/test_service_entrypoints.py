# Copyright 2026 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Regression tests for the abstract-service singleton bug.

Both sgc.meeting.transcription.service and sgc.meeting.notes.service are
AbstractModels, so callers reach them via self.env[...], which is always an
EMPTY recordset. Their entry points (transcribe/summarize) used to call
self.ensure_one(), which raised "Expected singleton: ..." on every call —
transcription failed on real recordings (session 163) and the notes pipeline
never produced a single record. These tests pin the entry points to work
without any self-record, with the HTTP backends mocked away.
"""

import base64
import json
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

_TX_SERVICE = "odoo.addons.sgc_meeting_ai.services.transcription_service"
_NOTES_SERVICE = "odoo.addons.sgc_meeting_ai.services.notes_service"


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = json.dumps(self._payload)

    def json(self):
        return self._payload


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestTranscriptionServiceEntrypoint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("sgc_meeting_ai.sgc_provider_in_person")
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_meeting_ai.transcription_backend", "cloud"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_meeting_ai.groq_api_key", "test-key"
        )

    def _make_recording(self):
        event = self.env["calendar.event"].create({
            "name": "Tx Test Meeting",
            "start": fields.Datetime.now(),
            "stop": fields.Datetime.now(),
        })
        session = self.env["sgc.meeting.session"].create({
            "meeting_id": event.id,
            "provider_id": self.provider.id,
        })
        attachment = self.env["ir.attachment"].create({
            "name": "meeting_test.mp3",
            "datas": base64.b64encode(b"fake audio bytes"),
            "mimetype": "audio/mpeg",
        })
        return self.env["sgc.meeting.recording"].create({
            "session_id": session.id,
            "attachment_id": attachment.id,
        })

    def test_transcribe_runs_without_self_record(self):
        """transcribe() must not raise the empty-recordset singleton error."""
        recording = self._make_recording()
        payload = {"text": "hello world", "language": "en", "duration": 5}
        with patch(
            f"{_TX_SERVICE}.requests.post",
            return_value=_FakeResponse(200, payload),
        ) as mock_post:
            result = self.env["sgc.meeting.transcription.service"].transcribe(
                recording
            )
        self.assertTrue(mock_post.called)
        self.assertEqual(result["text"], "hello world")
        self.assertEqual(result["language"], "en")


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestNotesServiceEntrypoint(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("sgc_meeting_ai.sgc_provider_in_person")
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_meeting_ai.orch_jwt_secret", "test-secret"
        )

    def _make_transcript(self):
        event = self.env["calendar.event"].create({
            "name": "Notes Test Meeting",
            "start": fields.Datetime.now(),
            "stop": fields.Datetime.now(),
        })
        session = self.env["sgc.meeting.session"].create({
            "meeting_id": event.id,
            "provider_id": self.provider.id,
        })
        return self.env["sgc.meeting.transcript"].create({
            "session_id": session.id,
            "text": "Prospect discussed budget and timeline.",
        })

    def test_summarize_runs_without_self_record(self):
        """summarize() must not raise the empty-recordset singleton error."""
        transcript = self._make_transcript()
        llm_content = json.dumps({
            "summary": "Discussed budget.",
            "key_points": "<ul><li>Budget</li></ul>",
            "decisions": "<ul></ul>",
            "action_items": "<ul></ul>",
            "risks": "<ul></ul>",
        })
        payload = {
            "choices": [{"message": {"content": llm_content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }
        with patch(
            f"{_NOTES_SERVICE}.requests.post",
            return_value=_FakeResponse(200, payload),
        ) as mock_post:
            notes = self.env["sgc.meeting.notes.service"].summarize(transcript)
        self.assertTrue(mock_post.called)
        self.assertTrue(notes)
        self.assertIn("Discussed budget.", notes.summary)
        self.assertEqual(notes.session_id, transcript.session_id)
