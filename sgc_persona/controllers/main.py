import json
import logging
import os

import requests

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

PERSONA_MODEL_MAP = {
    "finance_analyst": "auto",
    "aml_officer": "auto",
    "compliance_auditor": "auto",
    "data_analyst": "auto",
}

FREELLM_API_URL = os.environ.get(
    "FREELLM_API_URL",
    "http://host.docker.internal:3001/v1",
)
FREELLM_API_KEY = os.environ.get(
    "FREELLM_API_KEY",
    "freellmapi-2d41c7e3c3e323d702c337dd195dd1f7f2b4ae174de7830f",
)


class SgcPersonaController(http.Controller):

    @http.route(
        "/sgc/persona/generate",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def generate(self, **kwargs):
        persona_code = kwargs.get("persona_code", "auto")
        message = kwargs.get("message", "")

        assistant = request.env["llm.assistant"].search(
            [("code", "=", persona_code)], limit=1
        )

        system_prompt = ""
        if assistant and assistant.prompt_id:
            try:
                default_values = assistant.get_evaluated_default_values({})
                messages = assistant.prompt_id.get_messages(default_values)
                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                        break
            except Exception:
                _logger.exception("Failed to get system prompt for %s", persona_code)

        model = PERSONA_MODEL_MAP.get(persona_code, "auto")

        api_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FREELLM_API_KEY}",
        }

        payload = {
            "model": model,
            "messages": [],
            "stream": False,
        }

        if system_prompt:
            payload["messages"].append({"role": "system", "content": system_prompt})

        payload["messages"].append({"role": "user", "content": message})

        try:
            resp = requests.post(
                f"{FREELLM_API_URL}/chat/completions",
                headers=api_headers,
                json=payload,
                timeout=120,
            )
            result = resp.json()
            content = (
                result.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return request.make_json_response({
                "content": content,
                "persona_code": persona_code,
            })
        except Exception as e:
            _logger.exception("FreeLLM API error")
            return request.make_json_response({
                "error": str(e),
            }, status=500)

    @http.route(
        "/sgc/persona/start_chat",
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def start_chat(self, persona_code):
        try:
            assistant = request.env["llm.assistant"].search(
                [("code", "=", persona_code)], limit=1
            )
            if not assistant:
                return {"error": f"Persona '{persona_code}' not found"}

            return {
                "assistant_id": assistant.id,
                "name": assistant.name,
                "code": assistant.code,
            }
        except Exception as e:
            _logger.exception("Failed to start chat: %s", e)
            return {"error": str(e)}
