# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
CRM Executive Dashboard — Saved Filter
=======================================

Lets users persist their favourite dashboard filter combinations
so they can reload them with one click from the toolbar.

Unlike the export wizard, this model is **persistent** (not
transient) so saved filters survive across sessions.

Fields
------
* ``name``           — display name
* ``user_id``        — owner (defaults to current user)
* ``filter_dict``    — JSON string of the dashboard filter contract
* ``is_default``     — true = load on dashboard open
* ``shared``         — true = visible to other users (read-only)

API
---
* :meth:`action_apply` — returns a dict with the parsed filter
* :meth:`_ensure_one_default` — guarantees at most one default per user
"""

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.models import Constraint

_logger = logging.getLogger(__name__)


class CrmDashboardFilter(models.Model):
    _name = 'crm.dashboard.filter'
    _description = 'CRM Dashboard Saved Filter'
    _order = 'is_default desc, name asc'
    _rec_name = 'name'

    name = fields.Char('Filter Name', required=True)
    description = fields.Char('Description')

    user_id = fields.Many2one('res.users', string='Owner',
                              default=lambda self: self.env.user,
                              required=True, index=True, ondelete='cascade')

    filter_dict = fields.Text('Filter (JSON)', required=True,
                              default='{"period": "last_30_days"}',
                              help="JSON object with the same keys as the dashboard "
                                   "filter contract (period, date_from, date_to, "
                                   "user_id, team_id, source_id, stage_id, company_id).")

    is_default = fields.Boolean('Load on open', default=False, index=True)
    shared = fields.Boolean('Shared with all users', default=False, index=True)

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    color = fields.Integer('Color Index', default=0)

    # ------------------------------------------------------------------
    # Constraints (Odoo 19 prefers models.Constraint over _sql_constraints)
    # ------------------------------------------------------------------

    _name_user_unique = Constraint(
        'UNIQUE(name, user_id)',
        'You already have a saved filter with this name.',
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('filter_dict')
    def _check_filter_dict(self):
        for rec in self:
            if not rec.filter_dict:
                raise ValidationError(_("Filter dict cannot be empty."))
            try:
                d = json.loads(rec.filter_dict)
            except (ValueError, TypeError) as e:
                raise ValidationError(_("Filter must be valid JSON: %s") % e)
            if not isinstance(d, dict):
                raise ValidationError(_("Filter must be a JSON object."))
            # Whitelist allowed keys
            allowed = {'period', 'date_from', 'date_to', 'user_id',
                       'team_id', 'source_id', 'stage_id', 'company_id'}
            unknown = set(d.keys()) - allowed
            if unknown:
                raise ValidationError(
                    _("Unknown filter keys: %s") % ', '.join(sorted(unknown))
                )

    @api.constrains('is_default')
    def _check_one_default(self):
        for rec in self:
            if rec.is_default:
                others = self.search([
                    ('user_id', '=', rec.user_id.id),
                    ('is_default', '=', True),
                    ('id', '!=', rec.id),
                ])
                if others:
                    raise ValidationError(
                        _("You can only have one default filter. "
                          "Unset '%s' first.") % others[0].name
                    )

    # ------------------------------------------------------------------
    # Access overrides
    # ------------------------------------------------------------------

    def check_access(self, operation):
        """Users can only see their own filters + shared ones.

        Managers see all.
        """
        super().check_access(operation)
        if operation in ('read', 'write', 'unlink'):
            user = self.env.user
            is_manager = user.has_group(
                'crm_executive_dashboard.group_crm_dashboard_manager'
            )
            for rec in self:
                if is_manager:
                    continue
                if not rec.shared and rec.user_id != user:
                    raise AccessError(
                        _("You can only access your own filters.")
                    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_dict(self):
        """Parse the stored JSON into a clean dict."""
        self.ensure_one()
        try:
            d = json.loads(self.filter_dict or '{}')
        except (ValueError, TypeError):
            d = {}
        if not isinstance(d, dict):
            d = {}
        d.setdefault('period', 'last_30_days')
        return d

    def action_apply(self):
        """Return the parsed filter dict (used by RPC)."""
        self.ensure_one()
        return {
            'id': self.id,
            'name': self.name,
            'filter': self._parse_dict(),
            'is_default': self.is_default,
        }

    # ------------------------------------------------------------------
    # Search overrides
    # ------------------------------------------------------------------

    @api.model
    def search_for_user(self, domain=None, limit=None):
        """Default: return current user's filters + shared ones."""
        domain = domain or []
        user = self.env.user
        if not user.has_group('crm_executive_dashboard.group_crm_dashboard_manager'):
            domain = ['|', ('shared', '=', True), ('user_id', '=', user.id)] + domain
        return self.search(domain, limit=limit)

    # ------------------------------------------------------------------
    # Wizard-like helpers (used by the JS frontend)
    # ------------------------------------------------------------------

    @api.model
    def get_default_for_user(self):
        """Return the current user's default filter, or False."""
        user = self.env.user
        rec = self.search([
            ('user_id', '=', user.id),
            ('is_default', '=', True),
        ], limit=1)
        if not rec:
            return False
        return rec.action_apply()

    @api.model
    def create_from_payload(self, name, filter_dict, is_default=False):
        """Create a saved filter from a frontend payload."""
        return self.create({
            'name': name,
            'filter_dict': json.dumps(filter_dict or {}),
            'is_default': is_default,
            'user_id': self.env.user.id,
        })
