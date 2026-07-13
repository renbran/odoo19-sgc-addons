# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class PaymentApprovalHistory(models.Model):
    """
    Payment Approval History - Comprehensive Audit Trail
    
    Tracks complete approval workflow history for compliance and audit purposes.
    """
    _name = 'payment.approval.history'
    _description = 'Payment Approval History'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    
    # ============================================================================
    # CORE FIELDS
    # ============================================================================
    
    payment_id = fields.Many2one(
        'account.payment',
        string='Payment',
        required=True,
        ondelete='cascade',
        index=True,
        help="Related payment record"
    )
    
    # Workflow transition tracking
    stage_from = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('for_approval', 'For Approval'),
        ('for_authorization', 'For Authorization'),
        ('approved', 'Approved'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
        ('verified', 'Verified'),
    ], string='From Stage', required=True, help="Previous stage")
    
    stage_to = fields.Selection([
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('for_approval', 'For Approval'),
        ('for_authorization', 'For Authorization'),
        ('approved', 'Approved'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
        ('pending', 'Pending'),
        ('verified', 'Verified'),
    ], string='To Stage', required=True, help="New stage")
    
    action_type = fields.Selection([
        ('create', 'Create'),
        ('submit', 'Submit for Review'),
        ('review', 'Review'),
        ('approve', 'Approve'),
        ('authorize', 'Authorize'),
        ('verify', 'Verify'),
        ('reject', 'Reject'),
        ('post', 'Post'),
        ('cancel', 'Cancel'),
        ('reset', 'Reset to Draft'),
    ], string='Action Type', required=True, help="Type of action performed")
    
    # User and timing information
    user_id = fields.Many2one(
        'res.users',
        string='Performed By',
        required=True,
        default=lambda self: self.env.user,
        help="User who performed this action"
    )
    
    approval_date = fields.Datetime(  # For backward compatibility
        string='Action Date',
        required=True,
        default=fields.Datetime.now,
        help="When this action was performed"
    )
    
    # Additional context
    comments = fields.Text(
        string='Comments',
        help="Additional comments or reasons for this action"
    )
    
    ip_address = fields.Char(
        string='IP Address',
        help="IP address from which action was performed"
    )
    
    # ============================================================================
    # COMPUTED AND RELATED FIELDS
    # ============================================================================
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
        help="Human readable name for this history record"
    )
    
    duration_in_stage = fields.Float(
        string='Duration in Previous Stage (Hours)',
        compute='_compute_duration_in_stage',
        store=True,
        help="How long payment spent in previous stage"
    )
    
    company_id = fields.Many2one(
        related='payment_id.company_id',
        store=True,
        string='Company'
    )
    
    payment_voucher_number = fields.Char(
        related='payment_id.voucher_number',
        string='Voucher Number',
        store=True
    )
    
    payment_amount = fields.Monetary(
        related='payment_id.amount',
        currency_field='payment_currency_id',
        string='Amount',
        store=True
    )
    
    payment_currency_id = fields.Many2one(
        related='payment_id.currency_id',
        string='Currency',
        store=True
    )
    
    # ============================================================================
    # COMPUTE METHODS
    # ============================================================================
    
    @api.depends('payment_id', 'stage_from', 'stage_to', 'action_type', 'user_id')
    def _compute_display_name(self):
        """Compute display name for history records"""
        for record in self:
            payment_name = record.payment_voucher_number or record.payment_id.name or f"Payment #{record.payment_id.id}"
            action_desc = dict(record._fields['action_type'].selection)[record.action_type]
            user_name = record.user_id.name
            record.display_name = f"{payment_name} - {action_desc} by {user_name}"
    
    @api.depends('payment_id', 'stage_from', 'approval_date')
    def _compute_duration_in_stage(self):
        """Compute how long payment spent in previous stage"""
        for record in self:
            if not record.payment_id:
                record.duration_in_stage = 0.0
                continue
            
            # Find previous history record for same payment
            previous_record = self.search([
                ('payment_id', '=', record.payment_id.id),
                ('approval_date', '<', record.approval_date),
            ], order='approval_date desc', limit=1)
            
            if previous_record:
                time_diff = record.approval_date - previous_record.approval_date
                record.duration_in_stage = time_diff.total_seconds() / 3600.0
            else:
                # First record - duration from payment creation
                if record.payment_id.create_date:
                    time_diff = record.approval_date - record.payment_id.create_date
                    record.duration_in_stage = time_diff.total_seconds() / 3600.0
                else:
                    record.duration_in_stage = 0.0
    
    # ============================================================================
    # BUSINESS METHODS
    # ============================================================================
    
    def action_view_payment(self):
        """Action to view related payment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Payment - {self.payment_voucher_number}',
            'res_model': 'account.payment',
            'res_id': self.payment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def get_approval_statistics(self, date_from=None, date_to=None):
        """Get approval workflow statistics for reporting"""
        domain = []
        if date_from:
            domain.append(('approval_date', '>=', date_from))
        if date_to:
            domain.append(('approval_date', '<=', date_to))
        
        records = self.search(domain)
        
        # Statistics by action type
        action_stats = {}
        for action_type, label in self._fields['action_type'].selection:
            count = records.filtered(lambda r: r.action_type == action_type)
            action_stats[action_type] = {'label': label, 'count': len(count)}
        
        # Average duration by stage
        stage_durations = {}
        for stage, label in self._fields['stage_from'].selection:
            stage_records = records.filtered(lambda r: r.stage_from == stage)
            if stage_records:
                avg_duration = sum(stage_records.mapped('duration_in_stage')) / len(stage_records)
                stage_durations[stage] = {'label': label, 'avg_hours': round(avg_duration, 2)}
        
        # User activity
        user_activity = {}
        for user in records.mapped('user_id'):
            user_records = records.filtered(lambda r: r.user_id.id == user.id)
            user_activity[user.name] = len(user_records)
        
        return {
            'total_actions': len(records),
            'action_statistics': action_stats,
            'average_durations': stage_durations,
            'user_activity': user_activity,
            'date_range': {'from': date_from, 'to': date_to}
        }
    
    # ============================================================================
    # SECURITY AND AUDIT
    # ============================================================================
    
    def unlink(self):
        """Prevent deletion of approval history for audit compliance"""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Approval history records cannot be deleted for audit purposes"))
        return super().unlink()

    def write(self, vals):
        """Prevent modification of approval history for audit compliance"""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Approval history records cannot be modified for audit purposes"))
        return super().write(vals)
