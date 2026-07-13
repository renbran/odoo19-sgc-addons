# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import requests
import logging

_logger = logging.getLogger(__name__)


class SgcAIController(http.Controller):

    @http.route(
        '/sgc_ai_powerbox/get_response',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def get_response(self, **kwargs):
        """Receive prompt from Powerbox, forward to SGC AI backend, return response."""
        prompt = kwargs.get('prompt', '').strip()
        if not prompt:
            return {'error': 'No prompt provided.'}

        ICPSudo = request.env['ir.config_parameter'].sudo()
        api_endpoint = ICPSudo.get_param('sgc_ai.api_endpoint', '')
        api_key = ICPSudo.get_param('sgc_ai.api_key', '')
        model = ICPSudo.get_param('sgc_ai.model', 'MiniMax-M3')

        if not api_endpoint or not api_key:
            return {
                'error': (
                    'SGC AI not configured. Go to Settings \u2192 Technical \u2192 '
                    'System Parameters and set sgc_ai.api_endpoint and '
                    'sgc_ai.api_key.'
                )
            }

        payload = {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 500,
        }

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        try:
            _logger.info('SGC AI \u2192 sending to %s (model=%s)', api_endpoint, model)
            resp = requests.post(
                api_endpoint, json=payload, headers=headers, timeout=60
            )
            resp.raise_for_status()
            data = resp.json()

            ai_text = ''
            choices = data.get('choices', [])
            if choices:
                msg = choices[0].get('message', {})
                ai_text = msg.get('content', '')

            if not ai_text:
                ai_text = data.get('content', '') or data.get('response', '') or str(data)

            if not ai_text.strip():
                return {'error': 'AI returned empty response.'}

            return {'response': ai_text.strip()}

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
