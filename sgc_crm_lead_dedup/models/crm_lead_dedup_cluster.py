# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class CrmLeadDedupCluster(models.Model):
    _name = 'crm.lead.dedup.cluster'
    _description = 'CRM Lead Dedup - Duplicate Cluster (working queue)'
    _order = 'quarantined desc, member_count desc'

    name = fields.Char(compute='_compute_name', store=True)
    strategy = fields.Selection([
        ('s1_s2_combined', 'Tier 1 - Exact email and/or phone/mobile (combined graph)'),
        ('s3_company', 'S3 - Company identity (partner_name)'),
        ('s6_contact_trgm', 'S6 - contact_name trigram similarity'),
        ('s8_s9_partner_or_website', 'S8/S9 - Partner hierarchy or website domain match'),
    ], required=True, index=True)
    multi_open_deal = fields.Boolean(
        string='Multiple Open Deals (S5/S10)', default=False,
        help="2+ members are concurrently active opportunities at the same company — "
             "the 'one company, several live deals' case called out as a permanent "
             "review queue, not a separate detection strategy.")
    tier = fields.Selection([
        ('1', 'Tier 1 - Auto-merge eligible'),
        ('2', 'Tier 2 - Permanent human review'),
        ('3', 'Tier 3 - Manual only'),
    ], required=True, index=True)
    state = fields.Selection([
        ('pending_review', 'Pending Review'),
        ('approved', 'Approved for Merge'),
        ('merged', 'Merged'),
        ('rejected', 'Rejected (not a duplicate)'),
    ], default='pending_review', required=True, index=True)
    quarantined = fields.Boolean(default=False, help="10+ members: never auto-merged regardless of tier, requires manual inspection.")
    member_count = fields.Integer(compute='_compute_member_count', store=True)
    master_lead_id = fields.Many2one('crm.lead', string='Chosen Master', help="Filled in once the master-selection rule has run; not editable, informational.")
    master_rule_note = fields.Char(help="Which rule step chose the master, e.g. 'stage sequence' or 'oldest create_date (tiebreak)'.")
    line_ids = fields.One2many('crm.lead.dedup.cluster.line', 'cluster_id', string='Members')
    notes = fields.Text()
    merged_on = fields.Datetime()
    detection_label = fields.Integer(
        help="Internal connected-component label from the detection pass that "
             "created this cluster. Traceability only, not meaningful across re-runs.")

    @api.depends('line_ids')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.line_ids)

    @api.depends('strategy', 'member_count')
    def _compute_name(self):
        for rec in self:
            rec.name = f"{dict(rec._fields['strategy'].selection).get(rec.strategy, rec.strategy)} ({rec.member_count} members)"

    def action_approve(self):
        for rec in self:
            if rec.quarantined:
                raise UserError(f"Cluster {rec.id} is quarantined (10+ members) and must be inspected manually, not approved in bulk.")
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_to_pending(self):
        self.write({'state': 'pending_review'})


class CrmLeadDedupClusterLine(models.Model):
    _name = 'crm.lead.dedup.cluster.line'
    _description = 'CRM Lead Dedup - Cluster Member'
    _order = 'cluster_id, is_master desc'

    cluster_id = fields.Many2one('crm.lead.dedup.cluster', required=True, ondelete='cascade', index=True)
    lead_id = fields.Many2one('crm.lead', required=True, ondelete='cascade', index=True)
    is_master = fields.Boolean(default=False)
    stage_id = fields.Many2one(related='lead_id.stage_id', string='Stage')
    type = fields.Selection(related='lead_id.type')
    lead_create_date = fields.Datetime(related='lead_id.create_date', string='Lead Created On')
    # NOT named 'active': Odoo treats any field literally named 'active' as
    # the model's own archive flag, even when it's a related/non-stored
    # field — it silently adds a JOIN + WHERE lead.active IS TRUE to every
    # default search, hiding ~70% of real cluster_line rows (this is the
    # bug that made the detection queries below need a full active-only redo).
    lead_active = fields.Boolean(related='lead_id.active', string='Lead Active')

    _cluster_lead_uniq = models.Constraint(
        'unique(cluster_id, lead_id)',
        'A lead can only appear once per cluster.',
    )
