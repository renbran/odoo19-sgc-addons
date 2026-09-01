# -*- coding: utf-8 -*-
import logging
from datetime import timedelta
from odoo import models, fields

_logger = logging.getLogger(__name__)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    def _cron_cancel_overdue_crm(self):
        """Cancel CRM activities overdue by 14+ days."""
        today = fields.Date.context_today(self)
        cutoff = today - timedelta(days=14)

        overdue = self.search([
            ('res_model', '=', 'crm.lead'),
            ('date_done', '=', False),       # not completed
            ('date_deadline', '<', cutoff),   # overdue by 14+ days
        ])

        if overdue:
            _logger.info(
                'SGC Activity Lifecycle: cancelling %d CRM activities overdue 14+ days '
                '(cutoff=%s)',
                len(overdue), cutoff,
            )
            for activity in overdue:
                try:
                    activity.action_cancel()
                except Exception:
                    _logger.warning(
                        'SGC Activity Lifecycle: failed to cancel activity %d',
                        activity.id, exc_info=True,
                    )

        return True
