# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Whisper transcription service.

Supports two backends:

  1. ``cloud``  — Sends the audio file to a remote OpenAI-compatible
     Whisper endpoint (Groq by default). Costs ~$0.11 per hour of audio.

  2. ``local``  — Runs ``faster-whisper`` inside the Odoo container.
     Free, no API keys, no per-meeting cost. Slower than Groq but
     perfect for SGC's needs (1-hour meetings, ~30-90s transcription
     on a modern CPU).

Configuration (System Parameters or env vars):
  - sgc_meeting_ai.transcription_backend  (default: ``cloud``)
  - sgc_meeting_ai.groq_api_key           (cloud only)
  - sgc_meeting_ai.groq_api_base          (default https://api.groq.com/openai/v1)
  - sgc_meeting_ai.whisper_model          (default whisper-large-v3 / large-v3-turbo)
  - sgc_meeting_ai.local_whisper_model    (default large-v3-turbo, faster)
  - sgc_meeting_ai.local_whisper_device   (default cpu)
  - sgc_meeting_ai.local_whisper_compute  (default int8)
"""

import base64
import logging
import os
import subprocess
import tempfile

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SGCMetingTranscriptionService(models.AbstractModel):
    _name = "sgc.meeting.transcription.service"
    _description = "SGC Meeting Transcription Service"

    DEFAULT_CLOUD_MODEL = "whisper-large-v3"
    DEFAULT_LOCAL_MODEL = "large-v3-turbo"
    MAX_FILE_SIZE_MB = 100

    def _get_config(self):
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "backend": ICP.get_param("sgc_meeting_ai.transcription_backend") or "cloud",
            "api_key": ICP.get_param("sgc_meeting_ai.groq_api_key")
            or os.getenv("GROQ_API_KEY"),
            "api_base": ICP.get_param("sgc_meeting_ai.groq_api_base")
            or os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
            "model": ICP.get_param("sgc_meeting_ai.whisper_model")
            or self.DEFAULT_CLOUD_MODEL,
            "local_model": ICP.get_param("sgc_meeting_ai.local_whisper_model")
            or self.DEFAULT_LOCAL_MODEL,
            "local_device": ICP.get_param("sgc_meeting_ai.local_whisper_device")
            or "cpu",
            "local_compute": ICP.get_param("sgc_meeting_ai.local_whisper_compute")
            or "int8",
        }

    def transcribe(self, recording):
        """Transcribe a single recording, dispatching to the configured backend.

        Returns a dict:
            {
                "text": str,
                "language": str,
                "duration": int (seconds, if available),
                "model": str,
            }
        """
        self.ensure_one()
        if not recording.attachment_id:
            raise UserError(_("Recording has no attachment."))
        cfg = self._get_config()
        backend = cfg["backend"]
        _logger.info(
            "Transcribing recording %s via backend=%s model=%s",
            recording.id,
            backend,
            cfg["local_model"] if backend == "local" else cfg["model"],
        )
        if backend == "local":
            return self._transcribe_local(recording, cfg)
        return self._transcribe_cloud(recording, cfg)

    def _transcribe_cloud(self, recording, cfg):
        if not cfg["api_key"]:
            raise UserError(
                _(
                    "No GROQ_API_KEY configured. Set it in /opt/odoo-prod/.env "
                    "or in Settings → Technical → System Parameters "
                    "(sgc_meeting_ai.groq_api_key). Alternatively switch the "
                    "transcription backend to 'local'."
                )
            )
        if recording.file_size and recording.file_size > self.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise UserError(
                _(
                    "Recording too large (%s MB). Max: %s MB. "
                    "Split the file or upgrade to a higher-tier provider.",
                    round(recording.file_size / 1024 / 1024, 1),
                    self.MAX_FILE_SIZE_MB,
                )
            )
        attachment = recording.attachment_id
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(attachment.name or "")[1] or ".mp3"
        ) as tmp:
            tmp.write(base64.b64decode(attachment.datas))
            tmp_path = tmp.name
        try:
            url = f"{cfg['api_base'].rstrip('/')}/audio/transcriptions"
            with open(tmp_path, "rb") as audio_file:
                files = {"file": (attachment.name, audio_file)}
                data = {"model": cfg["model"], "response_format": "verbose_json"}
                if recording.language and recording.language != "auto":
                    data["language"] = recording.language
                headers = {"Authorization": f"Bearer {cfg['api_key']}"}
                response = requests.post(
                    url, headers=headers, files=files, data=data, timeout=300
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if response.status_code != 200:
            raise UserError(
                _("Whisper API error %s: %s", response.status_code, response.text[:500])
            )
        payload = response.json()
        text = payload.get("text", "")
        if not text:
            raise UserError(_("Whisper returned an empty response. Check the audio file."))
        return {
            "text": text.strip(),
            "language": payload.get("language", recording.language or "en"),
            "duration": int(payload.get("duration", 0)) or recording.duration_seconds or 0,
            "model": cfg["model"],
        }

    def _transcribe_local(self, recording, cfg):
        """Run faster-whisper in-process (free, no API calls)."""
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:
            raise UserError(
                _(
                    "Local Whisper backend selected but the 'faster-whisper' "
                    "Python package is not installed in the Odoo container. "
                    "Run: docker exec odoo-prod pip install faster-whisper --break-system-packages"
                )
            ) from exc
        model_size = cfg["local_model"]
        device = cfg["local_device"]
        compute_type = cfg["local_compute"]
        _logger.info(
            "Loading faster-whisper model=%s device=%s compute=%s",
            model_size,
            device,
            compute_type,
        )
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        attachment = recording.attachment_id
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(attachment.name or "")[1] or ".mp3",
        ) as tmp:
            tmp.write(base64.b64decode(attachment.datas))
            tmp_path = tmp.name
        try:
            language = recording.language if recording.language and recording.language != "auto" else None
            segments, info = model.transcribe(
                tmp_path,
                language=language,
                beam_size=5,
                vad_filter=True,
            )
            text_chunks = []
            for seg in segments:
                text_chunks.append(seg.text)
            text = " ".join(text_chunks).strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if not text:
            raise UserError(_("Local Whisper returned empty text. Check the audio."))
        return {
            "text": text,
            "language": getattr(info, "language", recording.language or "en"),
            "duration": int(getattr(info, "duration", 0)) or recording.duration_seconds or 0,
            "model": f"faster-whisper:{model_size}",
        }
