# -*- coding: utf-8 -*-
import json
from datetime import timedelta

from odoo import models, fields, api

_FAILURE_WINDOW_SECONDS = 60
_FAILURE_THRESHOLD = 5
_DEFAULT_BACKOFF_SECONDS = 60
_MAX_BACKOFF_SECONDS = 600


class LlmProvider(models.Model):
    _name = 'llm.provider'
    _description = 'LLM Provider'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    provider_type = fields.Selection([
        ('openai', 'OpenAI'),
        ('groq', 'Groq'),
        ('anthropic', 'Anthropic'),
        ('google', 'Google Gemini'),
        ('huggingface', 'HuggingFace'),
        ('mistral', 'Mistral AI'),
        ('minimax', 'MiniMax'),
        ('custom', 'Custom Endpoint'),
    ], string='Provider Type', required=True, default='openai')
    model_name = fields.Char(string='Model Name', required=True,
                             help='The model identifier (e.g. gpt-4, llama-3.3-70b)')
    api_key = fields.Char(string='API Key', required=True,
                          help='API authentication key')
    api_endpoint = fields.Char(string='Custom API Endpoint',
                               help='Base URL for custom API endpoint')
    temperature = fields.Float(string='Temperature', default=0.7,
                               help='Model temperature (0.0 - 1.0)')
    max_tokens = fields.Integer(string='Max Tokens', default=2000)
    timeout = fields.Integer(string='Timeout (seconds)', default=30)
    is_default = fields.Boolean(string='Default Provider',
                                help='Use as default provider for lead scoring')
    active = fields.Boolean(string='Active', default=True)
    total_requests = fields.Integer(string='Total Requests', default=0, readonly=True)
    failed_requests = fields.Integer(string='Failed Requests', default=0, readonly=True)
    last_used = fields.Datetime(string='Last Used', readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # ---- Circuit breaker (mirrors web.research.provider) -- a paid,
    # currently-misbehaving LLM provider must not get hammered by every
    # retry/cron worker; this is DB-backed (unlike llm.service's
    # process-local rate-limit cache) so it survives worker restarts.
    circuit_state = fields.Selection([
        ('closed', 'Closed'),
        ('open', 'Open'),
        ('half_open', 'Half-Open'),
    ], default='closed', readonly=True)
    circuit_open_until = fields.Datetime(readonly=True)
    circuit_backoff_seconds = fields.Integer(default=_DEFAULT_BACKOFF_SECONDS, readonly=True)
    failure_timestamps = fields.Text(default='[]', readonly=True)

    @api.model
    def get_default_provider(self):
        """Get the default active provider"""
        return self.search([('is_default', '=', True), ('active', '=', True)], limit=1)

    def is_available(self):
        """True if this provider isn't tripped by the circuit breaker."""
        self.ensure_one()
        if not self.active:
            return False
        self._cb_maybe_transition()
        return self.circuit_state != 'open'

    def _cb_maybe_transition(self):
        self.ensure_one()
        if (
            self.circuit_state == 'open'
            and self.circuit_open_until
            and fields.Datetime.now() >= self.circuit_open_until
        ):
            self.sudo().write({'circuit_state': 'half_open'})

    def _cb_record_success(self):
        self.ensure_one()
        self.sudo().write({
            'circuit_state': 'closed',
            'circuit_open_until': False,
            'circuit_backoff_seconds': _DEFAULT_BACKOFF_SECONDS,
            'failure_timestamps': '[]',
        })

    def _cb_record_failure(self):
        self.ensure_one()
        now = fields.Datetime.now()
        if self.circuit_state == 'half_open':
            backoff = min(self.circuit_backoff_seconds * 2, _MAX_BACKOFF_SECONDS)
            self.sudo().write({
                'circuit_state': 'open',
                'circuit_open_until': now + timedelta(seconds=backoff),
                'circuit_backoff_seconds': backoff,
            })
            return
        window_start = now - timedelta(seconds=_FAILURE_WINDOW_SECONDS)
        try:
            raw = json.loads(self.failure_timestamps or '[]')
            timestamps = [fields.Datetime.from_string(t) for t in raw]
        except (ValueError, TypeError):
            timestamps = []
        timestamps = [t for t in timestamps if t >= window_start]
        timestamps.append(now)
        vals = {'failure_timestamps': json.dumps([fields.Datetime.to_string(t) for t in timestamps])}
        if len(timestamps) >= _FAILURE_THRESHOLD:
            vals.update({
                'circuit_state': 'open',
                'circuit_open_until': now + timedelta(seconds=self.circuit_backoff_seconds),
            })
        self.sudo().write(vals)
