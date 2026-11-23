# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import logging
import re

_logger = logging.getLogger(__name__)

# Some models wrap their answer in a ```html ... ``` / ``` ... ``` code fence
# even when told not to. Strip it so the raw fragment reaches the editor.
_CODE_FENCE_RE = re.compile(r'^```(?:html)?\s*\n?(.*?)\n?```$', re.DOTALL)

# Some models (observed: MiniMax) occasionally narrate their own formatting
# plan in plain text before the real answer ("Let me analyze... I need to
# output only HTML, starting with <h4>, ..."), and since that narration
# mentions HTML tags unescaped, it visually corrupts the rendered field.
# Find the first well-formed, non-trivial heading -- >=4 chars of real
# content between an <h1>-<h6> open/close pair -- and treat everything
# before it as leaked narration to discard; the fake tag mentions inside a
# sentence don't have real closing content so they don't match this pattern.
_LEADING_PREAMBLE_RE = re.compile(
    r'^.*?(?=<h[1-6][^>]*>[^<]{4,}</h[1-6]>)', re.DOTALL | re.IGNORECASE
)

_DEFAULT_API_ENDPOINT = "http://freellmapi-prod:3001/v1/chat/completions"
_DEFAULT_MODEL = "nemotron-3-super-120b"

# MiniMax's OpenAI-compatible chat-completions endpoint (global region).
# https://platform.minimax.io/docs/api-reference/text-chat-openai
_MINIMAX_API_ENDPOINT = "https://api.minimax.io/v1/chat/completions"
_MINIMAX_MODEL = "MiniMax-M2.7"


class SgcAIController(http.Controller):

    @http.route(
        '/sgc_ai_powerbox/get_response',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_response(self, **kwargs):
        """Receive prompt from Powerbox, forward to SGC AI backend, return response.

        Context-aware: when invoked from an html_field (the powerbox flow), the
        JS sends a `context` dict with res_model, res_id, record_name, and the
        current field_text. We prepend a system message summarising that
        context so the model can answer with awareness of the open record.
        """
        prompt = (kwargs.get('prompt') or '').strip()
        context = kwargs.get('context') or {}
        provider = (kwargs.get('provider') or 'default').strip().lower()
        if not prompt:
            return {'error': 'No prompt provided.'}

        ICPSudo = request.env['ir.config_parameter'].sudo()
        if provider == 'minimax':
            api_endpoint = ICPSudo.get_param(
                'sgc_ai.minimax_endpoint', _MINIMAX_API_ENDPOINT
            )
            api_key = ICPSudo.get_param('sgc_ai.minimax_api_key', '')
            model = ICPSudo.get_param('sgc_ai.minimax_model', _MINIMAX_MODEL)
            missing_msg = (
                'MiniMax not configured. Go to Settings → Technical → '
                'System Parameters and set sgc_ai.minimax_api_key.'
            )
        else:
            api_endpoint = ICPSudo.get_param(
                'sgc_ai.api_endpoint', _DEFAULT_API_ENDPOINT
            )
            api_key = ICPSudo.get_param('sgc_ai.api_key', '')
            model = ICPSudo.get_param('sgc_ai.model', _DEFAULT_MODEL)
            missing_msg = (
                'SGC AI not configured. Go to Settings → Technical → '
                'System Parameters and set sgc_ai.api_endpoint and '
                'sgc_ai.api_key.'
            )

        if not api_endpoint or not api_key:
            return {'error': missing_msg}

        messages = self._build_messages(prompt, context)

        payload = {
            'model': model,
            'messages': messages,
            'temperature': 0.7,
            # 4096 covers the thinking budget of reasoning-heavy models
            # (e.g. DeepSeek V4 Flash) while still leaving room for a real
            # answer in the OpenAI-compatible content field.
            'max_tokens': 4096,
        }

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        try:
            _logger.info(
                'SGC AI → sending to %s (model=%s, ctx=%s)',
                api_endpoint, model,
                {k: v for k, v in context.items() if k != 'field_text'},
            )
            resp = requests.post(
                api_endpoint, json=payload, headers=headers, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            # MiniMax can return HTTP 200 with an error embedded in base_resp
            # (e.g. insufficient balance, invalid params) instead of a non-2xx
            # status code -- without this check that error looks like success.
            base_resp = data.get('base_resp') or {}
            if base_resp.get('status_code') not in (0, None):
                _logger.error(
                    'SGC AI (%s) base_resp error: %s', provider, base_resp,
                )
                return {
                    'error': 'AI service error: %s' % (
                        base_resp.get('status_msg') or base_resp
                    )
                }

            ai_text = ''
            choices = data.get('choices', [])
            if choices:
                msg = choices[0].get('message', {})
                ai_text = msg.get('content', '')

            if not ai_text:
                ai_text = data.get('content', '') or data.get('response', '') or str(data)

            ai_text = self._clean_html_response(ai_text)
            if not ai_text:
                return {'error': 'AI returned empty response.'}

            return {'response': ai_text}

        except requests.exceptions.Timeout:
            _logger.error('SGC AI request timed out after 60s')
            return {'error': 'AI service timed out. Try again later.'}
        except requests.exceptions.HTTPError as e:
            _logger.error('SGC AI HTTP error: %s', str(e))
            return {'error': f'AI service returned HTTP {e.response.status_code}.'}
        except requests.exceptions.ConnectionError:
            _logger.error('SGC AI connection failed to %s', api_endpoint)
            return {'error': 'Cannot reach AI service. Check sgc_ai.api_endpoint.'}
        except Exception as e:
            _logger.error('SGC AI unexpected error: %s', str(e))
            return {'error': f'Unexpected error: {str(e)}'}

    @staticmethod
    def _get_ai_enrichment_snapshot(res_model, res_id):
        """Best-effort read of any prior AI-enrichment data already stored on
        this record, straight from the DB.

        sgc_lead_scoring's crm.lead extension consistently prefixes every
        field it writes with 'ai_' (ai_enrichment_data, ai_scoring_rationale,
        ai_entity_type, the ai_*_score fields, etc.) -- reading by that naming
        convention avoids sgc_ai_powerbox having a hard manifest dependency on
        sgc_lead_scoring while still picking up its data when present.

        This is deliberately a DB read, not a read of the open form's DOM:
        the richest fields (ai_enrichment_data, the individual score fields)
        typically live on notebook tabs (AI Scoring, Executive Summary, ...)
        that aren't the active tab, so a DOM/form snapshot never sees them
        even though they're the most relevant grounding data for a request
        like "deep intelligence research" -- without this, the model has
        nothing but the current tab to go on and falls back to generic,
        assumption-based output instead of citing what was already found.
        """
        if not res_model or not res_id:
            return ''
        try:
            Model = request.env[res_model].sudo()
        except KeyError:
            return ''

        ai_field_names = [
            name for name, field in Model._fields.items()
            if name.startswith('ai_')
            and field.type in ('char', 'text', 'html', 'integer', 'float', 'boolean', 'selection')
        ]
        if not ai_field_names:
            return ''

        try:
            record = Model.browse(int(res_id))
            if not record.exists():
                return ''
            values = record.read(ai_field_names)[0]
        except Exception:
            _logger.exception(
                'SGC AI: failed reading ai_ fields for %s(%s)', res_model, res_id
            )
            return ''

        lines = []
        for name in ai_field_names:
            val = values.get(name)
            if val in (False, None, ''):
                continue
            text = str(val)
            # ai_enrichment_data is the full Universal JSON Contract from a
            # prior enrichment -- the single richest field, worth a much
            # bigger budget than the derived/summary fields around it.
            cap = 6000 if name == 'ai_enrichment_data' else 2000
            if len(text) > cap:
                text = text[:cap] + '…'
            lines.append(f'- {name}: {text}')
        return '\n'.join(lines)

    def _build_messages(self, prompt, context):
        """Compose the OpenAI-style messages array, optionally prepending a
        context system message describing the open record.
        """
        messages = [{'role': 'user', 'content': prompt}]
        res_model = context.get('res_model')
        res_id = context.get('res_id')
        record_name = context.get('record_name') or ''
        field_text = context.get('field_text') or ''

        format_lines = [
            'HARD RULE, apply before anything else below: the very first '
            'characters of your response must be an opening <h4> tag. Do not emit any '
            'sentence before it. Banned as a literal first sentence — do not '
            'write anything resembling these, in English or any other '
            'language: "Let me analyze...", "I will now...", "Here is a '
            'summary of...", "Based on the data provided...", or any '
            'restatement of the question. If you catch yourself about to '
            'write one of those, delete it and start with the <h4> instead.',
            'You are an AI assistant embedded in the Odoo ERP at SGC TECH, '
            'writing directly into a rich-text (WYSIWYG) HTML field for a '
            'business audience. The tone and structure must read as a '
            'professional report, not a chat reply.',
            'Respond ONLY with clean, semantic HTML — the response is inserted '
            'verbatim into the field, so it must render correctly with no '
            'further processing.',
            'Structure: <h4> title, then <h5> section headings that break the '
            'answer into clearly labeled parts (e.g. Overview, Key Facts, '
            'Assessment, Recommended Next Steps — pick headings that fit the '
            'actual question, not this exact list). Every section holds '
            'either prose <p> paragraphs or a <ul>/<ol> list, never a single '
            'wall of run-on text, and never more than 2-3 sentences run '
            'together without a break.',
            'When presenting known facts about a record (name, contact, '
            'revenue, scores, etc.), use a two-column '
            '<table><tbody><tr><td>Label</td><td>Value</td></tr>...'
            '</tbody></table> or a bulleted "<li><strong>Label:</strong> '
            'Value</li>" list, one fact per row/item — never a paragraph that '
            'chains many "Label: value Label: value" pairs in a row. Always a '
            'colon AND a space between label and value (write '
            '"<strong>Status:</strong> Won", never "Status:Won" or '
            '"<strong>Status</strong>Won").',
            'Use <table><thead><tr><th>...</th></tr></thead><tbody>...'
            '</tbody></table> for any genuinely tabular or comparison data; '
            '<strong> for emphasis inline within prose.',
            'Never use Markdown syntax (no **, no leading -, no #, no | tables). '
            'Never wrap the output in code fences or backticks. Never include '
            '<html>, <head>, <body>, or <!DOCTYPE> tags — return only the inner '
            'HTML fragment, ready to paste directly into the field.',
            'Never respond by asking the user to supply information — anything '
            'known about the record is already given to you below. Work with '
            'whatever is there: state findings and a best-effort assessment '
            'directly. If the available data is genuinely thin, say so in one '
            'short line and still deliver the most useful analysis you can '
            'from what is given; do not make an information request the whole '
            'answer.',
        ]

        if res_model:
            sys_lines = list(format_lines)
            sys_lines.append(
                f'The user is currently editing record: {res_model}'
                + (f' "{record_name}"' if record_name else '')
                + (f' (id={res_id})' if res_id else '')
            )
            ai_snapshot = self._get_ai_enrichment_snapshot(res_model, res_id)
            if ai_snapshot:
                sys_lines.append(
                    'Prior AI enrichment already stored on this record (from '
                    'an earlier AI Enrich run) — this is authoritative, '
                    'previously-researched structured intelligence about the '
                    'lead/record, not something to re-derive from scratch. '
                    'Ground your answer in it and cite it directly rather '
                    'than giving a generic, assumption-based response:\n'
                    f'{ai_snapshot}'
                )
            form_snapshot = (context.get('form_snapshot') or '')[:4000]
            if form_snapshot:
                sys_lines.append(
                    'Everything currently visible on the open form '
                    f'(all fields as displayed):\n{form_snapshot}'
                )
            if field_text:
                truncated = field_text[:1500]
                sys_lines.append(
                    f'Current field content (first 1500 chars):\n{truncated}'
                )
            sys_lines.append(
                'Use this context to make answers specific to the open record. '
                'Reminder before you write anything: first character output is '
                '"<", starting an <h4> tag — no lead-in sentence, no markdown, '
                'facts in a table or list with "Label: value" (colon + space), '
                'never bold-text-jammed-against-value.'
            )
            messages = [
                {'role': 'system', 'content': '\n\n'.join(sys_lines)},
                *messages,
            ]
        else:
            messages = [
                {'role': 'system', 'content': '\n\n'.join(format_lines)},
                *messages,
            ]
        return messages

    @staticmethod
    def _clean_html_response(ai_text):
        """Strip whitespace and any ```html / ``` code fence the model may
        have added despite being told not to, so a bare HTML fragment reaches
        the editor.
        """
        text = (ai_text or '').strip()
        fence_match = _CODE_FENCE_RE.match(text)
        if fence_match:
            text = fence_match.group(1).strip()

        preamble_match = _LEADING_PREAMBLE_RE.match(text)
        if preamble_match and preamble_match.group(0).strip():
            text = text[preamble_match.end():].strip()

        return text