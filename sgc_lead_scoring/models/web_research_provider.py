# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_BLOCKED_HOST_PREFIXES = (
    'localhost', '127.', '10.', '192.168.', '169.254.',
    '172.16.', '172.17.', '172.18.', '172.19.',
    '172.20.', '172.21.', '172.22.', '172.23.',
    '172.24.', '172.25.', '172.26.', '172.27.',
    '172.28.', '172.29.', '172.30.', '172.31.',
)
_BLOCKED_HOST_EXACT = ('0.0.0.0', '::1')

_FAILURE_WINDOW_SECONDS = 60
_FAILURE_THRESHOLD = 5
_DEFAULT_BACKOFF_SECONDS = 60
_MAX_BACKOFF_SECONDS = 600


class WebResearchProvider(models.Model):
    _name = 'web.research.provider'
    _inherit = ['mail.thread']
    _description = 'Web Research Provider'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    provider_type = fields.Selection([
        ('tavily', 'Tavily'),
        ('exa', 'Exa'),
        ('serper', 'Serper.dev'),
        ('serpapi', 'SerpAPI'),
        ('searxng', 'SearXNG (self-hosted)'),
        ('google', 'Google Custom Search (legacy)'),
    ], required=True)
    api_key = fields.Char(groups='base.group_system')
    search_engine_id = fields.Char(
        groups='base.group_system',
        help='Google Programmable Search Engine ID (google provider_type only)',
    )
    base_url = fields.Char(help='Required for searxng; self-hosted search endpoint URL')
    active = fields.Boolean(default=True)

    daily_quota_limit = fields.Integer(default=1000)
    daily_quota_used = fields.Integer(default=0, readonly=True)
    quota_reset_date = fields.Date(readonly=True)

    circuit_state = fields.Selection([
        ('closed', 'Closed'),
        ('open', 'Open'),
        ('half_open', 'Half-Open'),
    ], default='closed', readonly=True)
    circuit_open_until = fields.Datetime(readonly=True)
    circuit_backoff_seconds = fields.Integer(default=_DEFAULT_BACKOFF_SECONDS, readonly=True)
    failure_timestamps = fields.Text(default='[]', readonly=True)

    total_requests = fields.Integer(default=0, readonly=True)
    failed_requests = fields.Integer(default=0, readonly=True)
    last_used = fields.Datetime(readonly=True)

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.constrains('base_url')
    def _check_base_url_not_internal(self):
        for rec in self:
            if not rec.base_url:
                continue
            host = rec.base_url.split('//')[-1].split('/')[0].split(':')[0].lower()
            if host in _BLOCKED_HOST_EXACT or any(host.startswith(p) for p in _BLOCKED_HOST_PREFIXES):
                raise ValidationError(
                    _('base_url may not point to a localhost/private/link-local address: %s') % rec.base_url
                )

    def is_available(self):
        """True if this provider can be used right now."""
        self.ensure_one()
        if not self.active:
            return False
        self._cb_maybe_transition()
        if self.circuit_state == 'open':
            return False
        self._quota_maybe_reset()
        if self.daily_quota_used >= self.daily_quota_limit:
            return False
        return True

    @api.model
    def get_available_chain(self, provider_types=None):
        """Ordered recordset of active providers not OPEN/at-quota.

        Enforces the master kill switch (spec "Security & privacy ->
        Master kill switch"): when llm_lead_scoring.allow_third_party_search
        is not 'True' (default False on upgrade/fresh install), only
        provider_type='searxng' (self-hosted) may be returned, regardless
        of what the caller asked for.
        """
        allow_third_party = self.env['ir.config_parameter'].sudo().get_param(
            'llm_lead_scoring.allow_third_party_search', 'False'
        ) == 'True'
        if not allow_third_party:
            provider_types = ['searxng']
        domain = [('active', '=', True)]
        if provider_types:
            domain.append(('provider_type', 'in', provider_types))
        providers = self.search(domain, order='sequence, name')
        return providers.filtered(lambda p: p.is_available())

    # ---- Quota ----
    def _quota_maybe_reset(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.quota_reset_date != today:
            self.sudo().write({'daily_quota_used': 0, 'quota_reset_date': today})

    def _quota_increment(self):
        self.ensure_one()
        self._quota_maybe_reset()
        self.sudo().write({'daily_quota_used': self.daily_quota_used + 1})

    # ---- Circuit breaker ----
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

    def record_call(self, success):
        """Update stats counters + circuit breaker after a call attempt."""
        self.ensure_one()
        vals = {'total_requests': self.total_requests + 1, 'last_used': fields.Datetime.now()}
        if not success:
            vals['failed_requests'] = self.failed_requests + 1
        self.sudo().write(vals)
        if success:
            self._cb_record_success()
        else:
            self._cb_record_failure()
