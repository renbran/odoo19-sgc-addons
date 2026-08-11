from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class GamificationBadge(models.Model):
    _inherit = 'gamification.badge'

    point_value = fields.Integer(
        string='Point Value',
        default=0,
        help='Karma points awarded to a user each time this badge is granted.',
    )

    @api.model
    def _cron_award_top_earner(self):
        """Monthly: whoever has the highest won-deal revenue this month
        gets Top Earner. A relative ranking (not a threshold) can't be
        expressed as a standard goal_definition, so this runs as its own
        cron. Metric is expected_revenue on crm.lead reaching a won stage
        -- the plainest reading of "earner" until told otherwise."""
        badge = self.env.ref('sgc_employee_badges.badge_top_earner', raise_if_not_found=False)
        if not badge:
            return
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1)
        self.env.cr.execute("""
            SELECT user_id, SUM(expected_revenue) AS total
              FROM crm_lead
              JOIN crm_stage ON crm_stage.id = crm_lead.stage_id
             WHERE crm_stage.is_won = TRUE
               AND crm_lead.date_closed >= %s
               AND crm_lead.date_closed < %s
               AND crm_lead.user_id IS NOT NULL
          GROUP BY user_id
          ORDER BY total DESC
             LIMIT 1
        """, (month_start, month_end))
        row = self.env.cr.dictfetchone()
        if not row or not row['total']:
            return
        self.env['gamification.badge.user'].sudo().create({
            'badge_id': badge.id,
            'user_id': row['user_id'],
        })
