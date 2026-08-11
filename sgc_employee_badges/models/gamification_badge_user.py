from odoo import _, api, models


class GamificationBadgeUser(models.Model):
    _inherit = 'gamification.badge.user'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.badge_id.point_value and record.user_id:
                record.user_id.sudo()._add_karma(
                    record.badge_id.point_value,
                    reason=_('Badge: %s', record.badge_id.name),
                )
        return records
