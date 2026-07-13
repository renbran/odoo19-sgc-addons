from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Review'),
        ('reviewed', 'Reviewed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval State', default='draft', tracking=True)
    can_submit_for_review = fields.Boolean(compute='_compute_approval_flags')
    can_review = fields.Boolean(compute='_compute_approval_flags')
    can_approve = fields.Boolean(compute='_compute_approval_flags')
    can_post_manual = fields.Boolean(compute='_compute_approval_flags')

    @api.depends('approval_state', 'move_type', 'state')
    def _compute_approval_flags(self):
        for move in self:
            move.can_submit_for_review = (
                move.approval_state == 'draft' and move.state == 'draft'
            )
            move.can_review = (
                move.approval_state == 'submitted'
            )
            move.can_approve = (
                move.approval_state == 'reviewed'
            )
            move.can_post_manual = (
                move.approval_state == 'approved' and move.state == 'posted'
            )

    def action_submit_for_review(self):
        for move in self:
            move.approval_state = 'submitted'

    def action_review_approve(self):
        for move in self:
            move.approval_state = 'reviewed'

    def action_final_approve(self):
        for move in self:
            move.approval_state = 'approved'

    def action_reject_invoice_bill(self):
        for move in self:
            move.approval_state = 'rejected'
