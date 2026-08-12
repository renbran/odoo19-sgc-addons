# -*- coding: utf-8 -*-
from odoo import models


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

        for lead in dead_leads:
            message_count = MailMessage.search_count([
                ('res_id', '=', lead.id),
                ('model', '=', 'crm.lead'),
                ('message_type', '!=', 'notification'),
            ])

            if message_count >= 3:
                lead.write({'active': False})
                archived_count += 1
            else:
                current_owner = lead.user_id.id
                eligible_users = [uid for uid in team_user_ids if uid != current_owner]

                if not eligible_users:
                    skipped_count += 1
                    continue

                idx = lead.id % len(eligible_users)
                new_owner_id = eligible_users[idx]

                if new_owner_id:
                    lead.write({
                        'user_id': new_owner_id,
                        'stage_id': new_stage.id,
                    })
                    redistributed_count += 1

        return f"Archived: {archived_count}, Redistributed: {redistributed_count}, Skipped: {skipped_count}"
