# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
CRM Executive Dashboard — Scheduled Report Configuration
========================================================

A real persistence model that lets managers schedule recurring
dashboard exports (CSV / XLSX / PDF) and have them emailed to a
list of recipients.

Design
------
* ``frequency``  — daily / weekly / monthly
* ``day_of_week`` — 0..6 (Mon..Sun) for weekly
* ``day_of_month`` — 1..28 for monthly (cap at 28 to be safe)
* ``hour``, ``minute`` — time of day to send
* ``next_run``   — auto-computed whenever ``frequency`` changes
* ``last_run``   — stamped by the cron runner
* ``state``      — active / paused
* ``recipients`` — comma-separated emails (validated on save)
* ``filter_dict`` — JSON string with the same shape as the dashboard
  filter contract
* ``export_format`` — csv / xlsx / pdf

The cron entry lives in ``data/crm_dashboard_data.xml`` and calls
``action_run_scheduled_reports()`` once per hour.  That method
selects configs where ``state = 'active' AND next_run <= now()``,
generates the file via the export wizard, attaches it to a mail and
sends to all recipients, then computes the next ``next_run``.

Permissions: managers can create / write; users can only read.
"""

import base64
import json
import logging
from datetime import datetime, timedelta, time

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


_DOW = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]


class CrmDashboardReportConfig(models.Model):
    _name = 'crm.dashboard.report.config'
    _description = 'CRM Dashboard Scheduled Report'
    _order = 'state desc, name asc'
    _rec_name = 'name'

    name = fields.Char('Report Name', required=True)
    description = fields.Text('Description')

    # --- Schedule ------------------------------------------------
    frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Frequency', required=True, default='weekly')

    day_of_week = fields.Selection(_DOW, string='Day of Week', default='0')
    day_of_month = fields.Integer('Day of Month', default=1,
                                  help="1..28 (capped at 28 to be safe across all months)")
    hour = fields.Integer('Hour (24h)', default=8, help="0..23")
    minute = fields.Integer('Minute', default=0, help="0..59")

    next_run = fields.Datetime('Next Run', compute='_compute_next_run',
                                store=True, readonly=False, index=True)
    last_run = fields.Datetime('Last Run', readonly=True)
    state = fields.Selection([
        ('active', 'Active'),
        ('paused', 'Paused'),
    ], string='Status', default='active', required=True, index=True)

    # --- Output --------------------------------------------------
    export_format = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
    ], string='Format', required=True, default='xlsx')

    recipients = fields.Char('Recipients (comma-separated emails)',
                             required=True,
                             help="Comma-separated list of email addresses.")

    filter_dict = fields.Text('Filter (JSON)',
                              default='{"period": "last_30_days"}',
                              help="JSON dict using the same keys as the dashboard filter contract.")

    run_history_ids = fields.One2many(
        'crm.dashboard.report.run', 'config_id',
        string='Run History',
    )
    run_count = fields.Integer('Run Count', compute='_compute_run_count',
                                store=True)

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('recipients')
    def _check_recipients(self):
        for rec in self:
            if not rec.recipients:
                continue
            emails = [e.strip() for e in rec.recipients.split(',') if e.strip()]
            if not emails:
                raise ValidationError(_("Please provide at least one recipient."))
            for email in emails:
                if '@' not in email or '.' not in email.split('@')[-1]:
                    raise ValidationError(
                        _("Invalid email address: %s") % email
                    )

    @api.constrains('hour', 'minute', 'day_of_month')
    def _check_time(self):
        for rec in self:
            if not (0 <= (rec.hour or 0) <= 23):
                raise ValidationError(_("Hour must be between 0 and 23."))
            if not (0 <= (rec.minute or 0) <= 59):
                raise ValidationError(_("Minute must be between 0 and 59."))
            if rec.frequency == 'monthly':
                if not (1 <= (rec.day_of_month or 1) <= 28):
                    raise ValidationError(
                        _("Day of month must be between 1 and 28.")
                    )

    @api.constrains('filter_dict')
    def _check_filter_dict(self):
        for rec in self:
            if not rec.filter_dict:
                continue
            try:
                d = json.loads(rec.filter_dict)
                if not isinstance(d, dict):
                    raise ValueError("must be a JSON object")
            except (ValueError, TypeError) as e:
                raise ValidationError(
                    _("Filter must be a valid JSON object: %s") % e
                )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('frequency', 'day_of_week', 'day_of_month', 'hour', 'minute', 'state', 'last_run')
    def _compute_next_run(self):
        """Compute the next run datetime based on frequency + time of day.

        If a ``last_run`` exists and the config is still active, the
        next run is computed from that. Otherwise, from now().
        """
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != 'active':
                rec.next_run = False
                continue
            base = rec.last_run or now
            rec.next_run = rec._next_run_from(base)

    @api.depends('run_history_ids')
    def _compute_run_count(self):
        for rec in self:
            rec.run_count = len(rec.run_history_ids)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _next_run_from(self, base_dt):
        """Return the next datetime > base_dt matching this config.

        Always returns a datetime strictly after ``base_dt``. If the
        base is already past today's scheduled time, we roll forward
        by the appropriate period.
        """
        self.ensure_one()
        hour = int(self.hour or 0)
        minute = int(self.minute or 0)
        target_time = time(hour=hour, minute=minute)
        candidate = base_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base_dt:
            candidate += timedelta(days=1)

        if self.frequency == 'daily':
            return candidate

        if self.frequency == 'weekly':
            target_dow = int(self.day_of_week or 0)  # 0 = Monday
            while candidate.weekday() != target_dow:
                candidate += timedelta(days=1)
            return candidate

        if self.frequency == 'monthly':
            dom = min(int(self.day_of_month or 1), 28)
            year = candidate.year
            month = candidate.month
            # Try current month; if already past, roll to next month
            try:
                cand = candidate.replace(month=month, day=dom)
            except ValueError:
                cand = candidate
            if cand <= base_dt:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                try:
                    cand = candidate.replace(year=year, month=month, day=dom)
                except ValueError:
                    cand = candidate
            return cand

        return candidate

    def _parse_filter(self):
        """Parse and return the stored filter dict with safe defaults."""
        self.ensure_one()
        try:
            d = json.loads(self.filter_dict or '{}')
        except (ValueError, TypeError):
            d = {}
        if not isinstance(d, dict):
            d = {}
        d.setdefault('period', 'last_30_days')
        return d

    def _parse_recipients(self):
        self.ensure_one()
        return [e.strip() for e in (self.recipients or '').split(',')
                if e.strip()]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_activate(self):
        for rec in self:
            rec.write({'state': 'active'})
        return True

    def action_pause(self):
        for rec in self:
            rec.write({'state': 'paused'})
        return True

    def action_run_now(self):
        """Manually trigger this report."""
        self.ensure_one()
        return self._execute_run(manual=True)

    # ------------------------------------------------------------------
    # Run history record
    # ------------------------------------------------------------------

    def _execute_run(self, manual=False):
        """Generate the file, email it, and stamp the run history."""
        self.ensure_one()
        filt = self._parse_filter()
        recipients = self._parse_recipients()
        if not recipients:
            raise UserError(_("No valid recipients configured."))

        # Generate the file via the export wizard (sudo + cron context)
        try:
            export = self.env['crm.dashboard.export'].sudo().with_context(
                cron=True,
            )
            result = export.action_generate(filt, self.export_format)
        except Exception as e:
            _logger.exception("CED: scheduled report generation failed for %s", self.name)
            self.env['crm.dashboard.report.run'].sudo().create({
                'config_id': self.id,
                'state': 'failed',
                'manual': manual,
                'recipients': self.recipients,
                'error_message': str(e),
                'run_at': fields.Datetime.now(),
            })
            raise

        # Build email
        b64 = result.get('file_data')
        if not b64:
            raise UserError(_("Export produced no data."))
        try:
            content = base64.b64decode(b64)
        except Exception:
            content = b64.encode('utf-8') if isinstance(b64, str) else b64
        filename = result.get('filename') or f"dashboard.{self.export_format}"

        # Compose mail
        subject = "[CRM Dashboard] %s — %s" % (self.name, fields.Date.today())
        body = (
            "<p>Hello,</p>"
            "<p>Please find attached the <b>%s</b> dashboard export "
            "(%s).</p>"
            "<p>Period: <b>%s</b></p>"
            "<p>Generated: %s</p>"
        ) % (self.name, self.export_format.upper(), filt.get('period'),
             fields.Datetime.now())

        # Create the attachment first
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'datas': b64,
            'res_model': 'crm.dashboard.report.config',
            'res_id': self.id,
            'type': 'binary',
        })

        # Build recipients — resolve to partner records
        partner_ids = []
        for email in recipients:
            partner_ids.append(self._get_or_create_partner(email).id)

        mail = self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': ','.join(recipients),
            'recipient_ids': [(6, 0, partner_ids)],
            'attachment_ids': [(4, attachment.id)],
        })

        # Send
        try:
            mail.send(raise_exception=True)
            state = 'sent'
            error = False
        except Exception as e:
            _logger.exception("CED: scheduled report email failed for %s", self.name)
            state = 'failed'
            error = str(e)

        # Stamp run history
        self.env['crm.dashboard.report.run'].sudo().create({
            'config_id': self.id,
            'state': state,
            'manual': manual,
            'recipients': self.recipients,
            'filename': filename,
            'file_size': len(content),
            'run_at': fields.Datetime.now(),
            'error_message': error,
        })

        # Roll forward
        now = fields.Datetime.now()
        self.write({
            'last_run': now,
            'next_run': self._next_run_from(now),
        })

        return {
            'state': state,
            'filename': filename,
            'size': len(content),
            'recipients': len(recipients),
        }

    def _get_or_create_partner(self, email):
        """Find or create a partner for the given email."""
        Partner = self.env['res.partner'].sudo()
        partner = Partner.search([('email', '=', email)], limit=1)
        if partner:
            return partner
        return Partner.create({
            'name': email,
            'email': email,
            'company_type': 'person',
        })

    # ------------------------------------------------------------------
    # Cron entry point
    # ------------------------------------------------------------------

    @api.model
    def action_run_scheduled_reports(self):
        """Cron entry: run all configs whose next_run <= now()."""
        now = fields.Datetime.now()
        configs = self.search([
            ('state', '=', 'active'),
            ('next_run', '<=', now),
        ])
        results = {'total': len(configs), 'sent': 0, 'failed': 0}
        for cfg in configs:
            try:
                # Use a fresh cursor-friendly env (cron runs in a
                # separate transaction so we don't pollute the user
                # context with sudo'd state).
                res = cfg.with_user(self.env.user)._execute_run(manual=False)
                if res.get('state') == 'sent':
                    results['sent'] += 1
                else:
                    results['failed'] += 1
            except Exception as e:
                _logger.exception("CED: scheduled report run failed: %s", e)
                results['failed'] += 1
        _logger.info("CED: scheduled reports run: %s", results)
        return results


class CrmDashboardReportRun(models.Model):
    _name = 'crm.dashboard.report.run'
    _description = 'CRM Dashboard Scheduled Report Run'
    _order = 'run_at desc'
    _rec_name = 'run_at'

    config_id = fields.Many2one('crm.dashboard.report.config', string='Report',
                                 required=True, ondelete='cascade', index=True)
    run_at = fields.Datetime('Run At', required=True, default=fields.Datetime.now)
    state = fields.Selection([
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], string='State', required=True)
    manual = fields.Boolean('Manual Run')
    recipients = fields.Char('Recipients')
    filename = fields.Char('Filename')
    file_size = fields.Integer('Size (bytes)')
    error_message = fields.Text('Error')

    def action_view_config(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.dashboard.report.config',
            'view_mode': 'form',
            'res_id': self.config_id.id,
        }
