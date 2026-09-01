# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        res = super().write(vals)
        if 'user_id' in vals:
            for lead in self:
                # Find all non-done activities on this lead
                activities = self.env['mail.activity'].search([
                    ('res_model', '=', 'crm.lead'),
                    ('res_id', '=', lead.id),
                    ('date_done', '=', False),  # not completed
                ])
                if activities:
                    _logger.info(
                        'SGC Activity Lifecycle: clearing %d activities on lead %d '
                        '(id=%d) due to reassignment to user %s',
                        len(activities), lead.id, lead.id or 0,
                        vals.get('user_id'),
                    )
                    activities.unlink()
        return res
