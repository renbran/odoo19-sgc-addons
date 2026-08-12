# -*- coding: utf-8 -*-
"""
CRM Lead Redistribution Automation
---------------------------------
Server action + scheduled action to:
1. Find leads in "No Answer" or "Not Interested" stages
2. If touch_count (message count) >= 3: archive the lead
3. Otherwise: redistribute to a different owner (not the same as current owner)
"""
from odoo import models


class CrmLeadRedistribution(models.Model):
    _name = 'crm.lead.redistribution'
    _description = 'CRM Lead Redistribution Automation'

    def get_touch_count(self, lead_id):
        """Get the touch count for a lead based on message interactions."""
        return self.env['mail.message'].search_count([
            ('res_id', '=', lead_id),
            ('model', '=', 'crm.lead'),
            ('message_type', '!=', 'notification'),
        ])

    def redistribute_dead_leads(self):
        """
        Redistribute dead leads (No Answer / Not Interested) across sales team.
        - If lead has >= 3 message interactions, archive it
        - Otherwise, reassign to a different owner from the sales team
        """
        Lead = self.env['crm.lead']
        TeamMember = self.env['crm.team.member']
        Stage = self.env['crm.stage']
        MailMessage = self.env['mail.message']

        # Find only the main pipeline dead stages (No Answer and Not Interested)
        dead_stages = Stage.search([
            '|',
            ('name', 'ilike', 'no answer'),
            ('name', 'ilike', 'not interested'),
        ])

        if not dead_stages:
            return "No dead stages found"

        # Get all sales team members
        sales_team = TeamMember.search([
            ('crm_team_id.name', 'ilike', 'Sales')
        ])
        team_user_ids = [tm.user_id.id for tm in sales_team if tm.user_id and tm.user_id.active]

        if not team_user_ids:
            return "No active sales team members found"

        # Find leads/opportunities in dead stages that are still active
        dead_leads = Lead.search([
            ('stage_id', 'in', dead_stages.ids),
            ('active', '=', True),
        ])

        archived_count = 0
        redistributed_count = 0
        skipped_count = 0

        for lead in dead_leads:
            # Count touch interactions via message count (excluding notifications)
            message_count = MailMessage.search_count([
                ('res_id', '=', lead.id),
                ('model', '=', 'crm.lead'),
                ('message_type', '!=', 'notification'),
            ])

            if message_count >= 3:
                # Archive the lead after 3+ touches without conversion
                lead.write({'active': False})
                archived_count += 1
            else:
                # Redistribute to a different owner
                current_owner = lead.user_id.id
                eligible_users = [uid for uid in team_user_ids if uid != current_owner]

                if not eligible_users:
                    skipped_count += 1
                    continue

                # Round-robin based on lead ID to ensure even distribution
                idx = lead.id % len(eligible_users)
                new_owner_id = eligible_users[idx]

                if new_owner_id:
                    lead.write({'user_id': new_owner_id})
                    redistributed_count += 1

        return f"Archived: {archived_count}, Redistributed: {redistributed_count}, Skipped: {skipped_count}"
