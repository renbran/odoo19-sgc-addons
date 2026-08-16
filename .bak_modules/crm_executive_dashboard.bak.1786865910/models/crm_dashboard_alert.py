# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
CRM Executive Dashboard — Alert Rule
=====================================

Configurable threshold rules that the KPI engine consults to emit
dynamic alerts.  This complements the static alerts in the KPI
engine and lets executives tune sensitivity without code changes.

Supported rule types
--------------------
* ``lead_stale``       — alert when no new lead in N days
* ``opp_stale``        — alert when more than N open opps are stale
* ``pipeline_low``     — alert when pipeline value < threshold
* ``conversion_low``   — alert when conversion % < threshold
* ``overdue_followups`` — alert when more than N overdue follow-ups
* ``won_zero``         — alert when 0 won opps in N days
* ``no_activity``      — alert when no activity in N days

Each rule has:
* ``severity`` (info / warn / danger)
* ``threshold`` (numeric; meaning depends on ``rule_type``)
* ``message_template`` (Python format string; may use ``{value}``, ``{days}``, ``{threshold}``)
* ``active`` flag
* ``last_triggered`` (auto-stamped when the rule fires)

The KPI engine reads active rules in :meth:`CrmDashboardKpi._compute_alerts`
and merges them with the hardcoded alerts.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


_SEVERITY = [
    ('info', 'Info'),
    ('warn', 'Warning'),
    ('danger', 'Critical'),
]


class CrmDashboardAlertRule(models.Model):
    _name = 'crm.dashboard.alert.rule'
    _description = 'CRM Dashboard Alert Rule'
    _order = 'sequence, id'
    _rec_name = 'name'

    name = fields.Char('Rule Name', required=True)
    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True, index=True)

    rule_type = fields.Selection([
        ('lead_stale', 'No new leads (days)'),
        ('opp_stale', 'Stale open opportunities'),
        ('pipeline_low', 'Pipeline value below threshold'),
        ('conversion_low', 'Lead conversion below threshold %'),
        ('overdue_followups', 'Overdue follow-ups'),
        ('won_zero', 'No won opportunities (days)'),
        ('no_activity', 'No activity (days)'),
    ], string='Rule Type', required=True, index=True)

    threshold = fields.Float('Threshold', required=True, default=10.0,
                             help="Numeric threshold.  Meaning depends on rule_type: "
                                  "days for stale/zero rules, count for stale-opps/overdue, "
                                  "currency for pipeline_low, percent for conversion_low.")

    severity = fields.Selection(_SEVERITY, string='Severity', required=True,
                                default='warn', index=True)

    message_template = fields.Char(
        'Message Template', required=True,
        default='{title}: {value} {unit} (threshold {threshold})',
        help="Python format string. Available placeholders: {value}, {days}, "
             "{threshold}, {title}, {unit}.",
    )

    last_triggered = fields.Datetime('Last Triggered', readonly=True)
    trigger_count = fields.Integer('Times Triggered', default=0, readonly=True)

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @api.constrains('threshold')
    def _check_threshold(self):
        for rec in self:
            if rec.threshold is None or rec.threshold < 0:
                raise ValueError(_("Threshold must be a non-negative number."))

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_evaluate(self):
        """Manually evaluate this rule against current data."""
        self.ensure_one()
        kpi_model = self.env['crm.dashboard.kpi']
        payload = kpi_model.collect_all({'period': 'last_30_days'})
        alerts = self._evaluate_payload(payload)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Alert Rule Evaluation'),
                'message': _('This rule would emit %d alert(s).') % len(alerts),
                'type': 'success' if alerts else 'info',
                'sticky': False,
            },
        }

    # ------------------------------------------------------------------
    # Evaluation engine — called by KPI model
    # ------------------------------------------------------------------

    def _evaluate_payload(self, payload):
        """Return a list of alert dicts this rule emits for the given payload.

        Each alert is a dict with keys: ``title``, ``message``,
        ``level`` (info/warn/danger), ``code``.
        """
        self.ensure_one()
        result = []
        threshold = float(self.threshold or 0)
        startup = payload.get('startup', {}) or {}
        health = startup.get('business_health', {}) or {}
        risk = startup.get('risk', {}) or {}
        kpi = payload.get('kpi', {}) or {}
        revenue = kpi.get('revenue', {}) or {}
        conversion = kpi.get('conversion', {}) or {}
        activity = payload.get('activity', {}) or {}

        if self.rule_type == 'lead_stale':
            days = int(health.get('days_since_lead') or 0)
            if days >= threshold:
                result.append(self._format(
                    value=days, days=days, threshold=threshold,
                    unit='days without new lead',
                    title='Lead pipeline drying up',
                ))

        elif self.rule_type == 'opp_stale':
            count = int(risk.get('stagnant_opps') or 0)
            if count >= threshold:
                result.append(self._format(
                    value=count, days=0, threshold=threshold,
                    unit='stale opportunities',
                    title='Stale opportunities in pipeline',
                ))

        elif self.rule_type == 'pipeline_low':
            value = float(revenue.get('pipeline_value') or 0)
            if value < threshold:
                result.append(self._format(
                    value=value, days=0, threshold=threshold,
                    unit='in pipeline',
                    title='Pipeline value below threshold',
                ))

        elif self.rule_type == 'conversion_low':
            value = float(conversion.get('lead_conversion_rate') or 0)
            if value < threshold:
                result.append(self._format(
                    value=value, days=0, threshold=threshold,
                    unit='% conversion',
                    title='Lead conversion rate low',
                ))

        elif self.rule_type == 'overdue_followups':
            count = int(risk.get('overdue_followups') or 0)
            if count >= threshold:
                result.append(self._format(
                    value=count, days=0, threshold=threshold,
                    unit='overdue follow-ups',
                    title='Overdue follow-ups',
                ))

        elif self.rule_type == 'won_zero':
            days = int(health.get('days_since_won_opp') or 0)
            if days >= threshold:
                result.append(self._format(
                    value=days, days=days, threshold=threshold,
                    unit='days without a win',
                    title='No won opportunities',
                ))

        elif self.rule_type == 'no_activity':
            monthly = activity.get('monthly', {}) or {}
            total = sum(int(monthly.get(k) or 0) for k in
                        ('calls', 'meetings', 'emails', 'other'))
            # If total is below threshold *and* there's at least one open opp
            open_opps = int(kpi.get('opportunities', {}).get('open') or 0)
            if total < threshold and open_opps > 0:
                result.append(self._format(
                    value=total, days=0, threshold=threshold,
                    unit='activities this month',
                    title='Low sales activity',
                ))

        if result:
            self.sudo().write({
                'last_triggered': fields.Datetime.now(),
                'trigger_count': self.trigger_count + 1,
            })
        return result

    def _format(self, **kwargs):
        """Build a single alert dict from the rule template."""
        self.ensure_one()
        try:
            message = self.message_template.format(**kwargs)
        except (KeyError, IndexError, ValueError) as e:
            message = f"{kwargs.get('title', self.name)}: {e}"
        return {
            'title': self.name,
            'message': message,
            'level': self.severity,
            'code': f'rule.{self.rule_type}',
        }
