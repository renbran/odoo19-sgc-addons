import requests
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SUPPORTED_PROVIDERS = {
    'openai': {
        'name': 'OpenAI',
        'default_endpoint': 'https://api.openai.com/v1/chat/completions',
        'model_key': 'model',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temp,
            'max_tokens': max_tokens,
        },
        'response_parser': lambda resp: resp.json()['choices'][0]['message']['content'],
    },
    'groq': {
        'name': 'Groq (via freellmapi gateway)',
        'default_endpoint': 'http://freellmapi:3001/v1/chat/completions',
        'model_key': 'model',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temp,
            'max_tokens': max_tokens,
        },
        'response_parser': lambda resp: resp.json()['choices'][0]['message']['content'],
    },
    'anthropic': {
        'name': 'Anthropic',
        'default_endpoint': 'https://api.anthropic.com/v1/messages',
        'model_key': 'model',
        'auth_header': 'x-api-key',
        'auth_prefix': '',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens,
        },
        'response_parser': lambda resp: resp.json()['content'][0]['text'],
    },
    'google': {
        'name': 'Google Gemini',
        'default_endpoint': 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
        'model_key': None,
        'auth_header': 'x-goog-api-key',
        'auth_prefix': '',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': temp,
                'maxOutputTokens': max_tokens,
            },
        },
        'response_parser': lambda resp: resp.json()['candidates'][0]['content']['parts'][0]['text'],
    },
    'huggingface': {
        'name': 'HuggingFace',
        'default_endpoint': 'https://api-inference.huggingface.co/models/{model}',
        'model_key': None,
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'inputs': prompt,
            'parameters': {
                'temperature': temp,
                'max_new_tokens': max_tokens,
            },
        },
        'response_parser': lambda resp: resp.json()[0]['generated_text'],
    },
    'mistral': {
        'name': 'Mistral AI',
        'default_endpoint': 'https://api.mistral.ai/v1/chat/completions',
        'model_key': 'model',
        'auth_header': 'Authorization',
        'auth_prefix': 'Bearer ',
        'data_template': lambda model, prompt, temp, max_tokens, timeout: {
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temp,
            'max_tokens': max_tokens,
        },
        'response_parser': lambda resp: resp.json()['choices'][0]['message']['content'],
    },
}

class LlmProvider(models.Model):
    _name = 'llm.provider'
    _description = 'LLM Provider Configuration'
    _order = 'sequence, name'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    provider_type = fields.Selection([
        ('openai', 'OpenAI'),
        ('groq', 'Groq'),
        ('anthropic', 'Anthropic'),
        ('google', 'Google Gemini'),
        ('huggingface', 'HuggingFace'),
        ('mistral', 'Mistral AI'),
        ('custom', 'Custom API'),
    ], string='Provider Type', required=True, default='openai')
    model_name = fields.Char(string='Model Name', required=True,
                              help='Model identifier (e.g. gpt-4-turbo-preview, llama-3.3-70b-versatile)')
    api_key = fields.Char(string='API Key', required=True)
    api_endpoint = fields.Char(string='API Endpoint',
                                help='Custom endpoint URL (only for Custom API type)')
    temperature = fields.Float(string='Temperature', default=0.7)
    max_tokens = fields.Integer(string='Max Tokens', default=2000)
    timeout = fields.Integer(string='Timeout (seconds)', default=30)
    active = fields.Boolean(string='Active', default=True)
    is_default = fields.Boolean(string='Is Default')
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)
    total_requests = fields.Integer(string='Total Requests', default=0)
    failed_requests = fields.Integer(string='Failed Requests', default=0)
    last_used = fields.Datetime(string='Last Used')

    _unique_default_per_company = models.Constraint(
        'UNIQUE(is_default, company_id)',
        'Only one provider can be default per company!',
    )

    @api.constrains('temperature')
    def _check_temperature(self):
        for record in self:
            if record.temperature < 0.0 or record.temperature > 2.0:
                raise ValidationError(_('Temperature must be between 0.0 and 2.0'))

    @api.constrains('max_tokens')
    def _check_max_tokens(self):
        for record in self:
            if record.max_tokens < 1:
                raise ValidationError(_('Max tokens must be greater than 0'))

    @api.model
    def get_default_provider(self):
        provider = self.search([('is_default', '=', True), ('active', '=', True)], limit=1)
        if not provider:
            provider = self.search([('active', '=', True)], limit=1)
        return provider

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_default'):
                self.search([('is_default', '=', True)]).write({'is_default': False})
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_default'):
            self.search([('is_default', '=', True)]).write({'is_default': False})
        return super().write(vals)

    def action_test_connection(self):
        self.ensure_one()
        try:
            result = self._make_request('Test connection. Respond with exactly: OK')
            if result.strip().upper() == 'OK' or 'OK' in result:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to %s') % self.name,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Warning'),
                    'message': _('Connected but unexpected response: %s') % result[:200],
                    'type': 'warning',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': _('Error: %s') % str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def _make_request(self, prompt):
        self.ensure_one()
        config = SUPPORTED_PROVIDERS.get(self.provider_type)
        if not config and self.provider_type != 'custom':
            raise UserError(_('Unsupported provider type: %s') % self.provider_type)

        headers = {'Content-Type': 'application/json'}

        if self.provider_type == 'custom':
            if not self.api_endpoint:
                raise UserError(_('Custom provider requires an API endpoint'))
            endpoint = self.api_endpoint
            headers[self.auth_header or 'Authorization'] = (self.auth_prefix or '') + self.api_key
            data = json.loads(self.data_template) if hasattr(self, 'data_template') else {}
        else:
            endpoint = self.api_endpoint or config['default_endpoint']
            endpoint = endpoint.replace('{model}', self.model_name or '')
            headers[config['auth_header']] = config['auth_prefix'] + self.api_key
            data = config['data_template'](self.model_name, prompt, self.temperature, self.max_tokens, self.timeout)

        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=data,
                timeout=self.timeout,
            )
            response.raise_for_status()
            self.total_requests += 1
            self.last_used = fields.Datetime.now()

            if self.provider_type == 'custom':
                return response.text
            return config['response_parser'](response)

        except requests.exceptions.Timeout:
            self.failed_requests += 1
            raise UserError(_('Request timed out after %d seconds') % self.timeout)
        except requests.exceptions.HTTPError as e:
            self.failed_requests += 1
            _logger.error('LLM provider HTTP error: %s - %s', self.name, str(e))
            raise UserError(_('HTTP error: %s') % str(e))
        except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
            self.failed_requests += 1
            _logger.error('LLM provider connection error: %s - %s', self.name, str(e))
            raise UserError(_('Connection error: %s') % str(e))
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            self.failed_requests += 1
            _logger.error('LLM provider parse error: %s - %s', self.name, str(e))
            raise UserError(_('Failed to parse response: %s') % str(e))
