# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLeadRedistribution(models.Model):
    _name = 'crm.lead.redistribution'
    _description = 'CRM Lead Redistribution Automation'

    def redistribute_dead_leads(self):
        Lead = self.env['crm.lead']
        TeamMember = self.env['crm.team.member']
        Stage = self.env['crm.stage']
        MailMessage = self.env['mail.message']

        dead_stages = Stage.search([('id', 'in', [5, 7])])

        if not dead_stages:
            return "No dead stages found"

        sales_team = TeamMember.search([('crm_team_id.name', 'ilike', 'Sales')])
        team_user_ids = [tm.user_id.id for tm in sales_team if tm.user_id and tm.user_id.active]

        if not team_user_ids:
            return "No active sales team members found"

        new_stage = Stage.search([('id', '=', 1)], limit=1)

        dead_leads = Lead.search([
            ('stage_id', 'in', dead_stages.ids),
            ('active', '=', True),
        ])

        archived_count = 0
        redistributed_count = 0
        skipped_count = 0

        # TRUE round-robin: use a counter, not lead.id
        user_index = 0

        for lead in dead_leads:
            # Only count messages created AFTER last redistribution
            # If never redistributed (last_redistribution_date is False/null), count all messages
            last_redist = lead.last_redistribution_date

            if last_redist:
                message_domain = [
                    ('res_id', '=', lead.id),
                    ('model', '=', 'crm.lead'),
                    ('message_type', '!=', 'notification'),
                    ('create_date', '>', last_redist),
                ]
            else:
                # Never redistributed - count all messages (initial touches)
                message_domain = [
                    ('res_id', '=', lead.id),
                    ('model', '=', 'crm.lead'),
                    ('message_type', '!=', 'notification'),
                ]

            message_count = MailMessage.search_count(message_domain)

            if message_count >= 3:
                lead.write({'active': False})
                archived_count += 1
            else:
                current_owner = lead.user_id.id
                eligible_users = [uid for uid in team_user_ids if uid != current_owner]

                if not eligible_users:
                    skipped_count += 1
                    continue

                # TRUE round-robin: cycle through users evenly
                new_owner_id = eligible_users[user_index % len(eligible_users)]
                user_index += 1

                if new_owner_id:
                    lead.write({
                        'user_id': new_owner_id,
                        'stage_id': new_stage.id,
                        'last_redistribution_date': fields.Datetime.now(),
                    })
                    redistributed_count += 1

        return "Archived: %s, Redistributed: %s, Skipped: %s" % (archived_count, redistributed_count, skipped_count)
