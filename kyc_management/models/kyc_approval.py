# -*- coding: utf-8 -*-
"""
KYC Approval Model
Manages KYC application approval workflow and officer assignments
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class KYCApproval(models.Model):
    """
    KYC Approval Model
    
    Tracks the approval workflow for KYC applications.
    Links officers to applications and manages approval decisions.
    """
    
    _name = 'kyc.approval'
    _description = 'KYC Approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'
    
    # ==================== RELATIONSHIPS ====================
    
    kyc_application_id = fields.Many2one(
        'kyc.application',
        string='KYC Application',
        required=True,
        ondelete='cascade',
        help='Link to the KYC application being approved'
    )
    
    approver_id = fields.Many2one(
        'res.users',
        string='Approver Officer',
        required=True,
        ondelete='restrict',
        help='Compliance officer assigned to review this application'
    )
    
    # ==================== APPROVAL WORKFLOW ====================
    
    approval_step = fields.Selection([
        ('initial_check', 'Initial Check'),
        ('document_verification', 'Document Verification'),
        ('risk_assessment', 'Risk Assessment'),
        ('final_approval', 'Final Approval'),
    ], string='Approval Step', default='initial_check', required=True,
       help='Current step in the approval process', tracking=True)
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('needs_clarification', 'Needs Clarification'),
    ], string='Status', default='pending', required=True,
       help='Current approval status', tracking=True)
    
    # ==================== REVIEW INFORMATION ====================
    
    # Initial Check
    documents_complete = fields.Boolean(
        string='Documents Complete',
        default=False,
        help='Are all required documents provided?'
    )
    
    documents_complete_notes = fields.Text(
        string='Documents Notes',
        help='Notes about document completeness'
    )
    
    # Document Verification
    documents_verified = fields.Boolean(
        string='Documents Verified',
        default=False,
        help='Have documents been verified as authentic?'
    )
    
    document_verification_notes = fields.Text(
        string='Document Verification Notes',
        help='Details about document verification process'
    )
    
    # Risk Assessment
    risk_score = fields.Integer(
        string='Risk Score',
        default=0,
        help='Risk assessment score (0-100)'
    )
    
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ], string='Risk Level', compute='_compute_risk_level', store=True,
       help='Risk classification based on assessment')
    
    risk_assessment_notes = fields.Text(
        string='Risk Assessment Notes',
        help='Detailed risk assessment comments'
    )
    
    # PEP Verification
    pep_check_performed = fields.Boolean(
        string='PEP Check Performed',
        default=False,
        help='Has PEP (Politically Exposed Person) check been done?'
    )
    
    pep_check_result = fields.Selection([
        ('none', 'Not Applicable'),
        ('clear', 'Clear - No PEP'),
        ('potential', 'Potential PEP - Further Review'),
        ('confirmed', 'Confirmed PEP'),
    ], string='PEP Check Result', default='none',
       help='Result of PEP verification')
    
    pep_verification_notes = fields.Text(
        string='PEP Verification Notes',
        help='Notes from PEP verification process'
    )
    
    # Sanctions Check
    sanctions_check_performed = fields.Boolean(
        string='Sanctions Check Performed',
        default=False,
        help='Has sanctions list check been performed?'
    )
    
    sanctions_check_result = fields.Selection([
        ('not_checked', 'Not Checked'),
        ('clear', 'Clear - No Matches'),
        ('potential_match', 'Potential Match'),
        ('confirmed_match', 'Confirmed Match'),
    ], string='Sanctions Check Result', default='not_checked',
       help='Result of sanctions list verification')
    
    sanctions_verification_notes = fields.Text(
        string='Sanctions Check Notes',
        help='Notes from sanctions verification'
    )

    source_of_funds_verified = fields.Boolean(
        string='Source of Funds Verified',
        default=False,
        help='Has the source of funds been reviewed and verified?'
    )

    source_of_wealth_verified = fields.Boolean(
        string='Source of Wealth Verified',
        default=False,
        help='Has the source of wealth been reviewed and verified?'
    )

    signature_verified = fields.Boolean(
        string='Signature Verified',
        default=False,
        help='Has applicant signature authenticity been verified?'
    )

    consent_verified = fields.Boolean(
        string='Consents Verified',
        default=False,
        help='Have all mandatory applicant consents been verified?'
    )
    
    # ==================== APPROVAL/REJECTION ====================
    
    review_start_date = fields.Datetime(
        string='Review Start Date',
        help='When the approval process started'
    )
    
    review_end_date = fields.Datetime(
        string='Review End Date',
        help='When the review was completed'
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        help='When the application was approved'
    )
    
    approval_notes = fields.Text(
        string='Approval Notes',
        help='Final comments on approval'
    )
    
    rejection_date = fields.Datetime(
        string='Rejection Date',
        help='When the application was rejected'
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        help='Why the application was rejected'
    )
    
    rejection_suggestions = fields.Text(
        string='Corrections Required',
        help='Suggestions for correction and resubmission'
    )
    
    # ==================== ACTIVITY TRACKING ====================
    
    conditions_for_approval = fields.Text(
        string='Conditions for Approval',
        help='Any conditions attached to the approval'
    )
    
    reviewer_comments = fields.Text(
        string='Reviewer Comments',
        help='Detailed comments from the reviewing officer',
        tracking=True
    )
    
    # ==================== ESCALATION ====================
    
    requires_escalation = fields.Boolean(
        string='Requires Escalation',
        default=False,
        help='Does this require escalation to a senior officer?',
        tracking=True
    )
    
    escalated_to_id = fields.Many2one(
        'res.users',
        string='Escalated To',
        help='Senior officer this was escalated to'
    )
    
    escalation_reason = fields.Text(
        string='Escalation Reason',
        help='Why this was escalated'
    )
    
    escalation_date = fields.Datetime(
        string='Escalation Date',
        help='When escalation occurred'
    )
    
    # ==================== CLARIFICATION REQUESTS ====================
    
    clarification_requested = fields.Boolean(
        string='Clarification Requested',
        default=False,
        help='Has clarification been requested from applicant?',
        tracking=True
    )
    
    clarification_request_date = fields.Datetime(
        string='Clarification Request Date',
        help='When clarification was requested'
    )
    
    clarification_details = fields.Text(
        string='Clarification Request Details',
        help='What clarification is needed'
    )
    
    clarification_response = fields.Text(
        string='Applicant Response',
        help='Applicant\'s response to clarification request'
    )
    
    clarification_response_date = fields.Datetime(
        string='Response Date',
        help='When applicant provided clarification'
    )
    
    clarification_acceptor_id = fields.Many2one(
        'res.users',
        string='Clarification Reviewed By',
        help='Officer who reviewed the clarification'
    )
    
    # ==================== AUDIT TRAIL ====================
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Actually Approved By',
        readonly=True,
        help='User who made the final approval decision'
    )
    
    rejected_by_id = fields.Many2one(
        'res.users',
        string='Rejected By',
        readonly=True,
        help='User who made the rejection decision'
    )
    
    # ==================== COMPUTED FIELDS ====================
    
    partner_name = fields.Char(
        string='Applicant Name',
        related='kyc_application_id.partner_id.name',
        readonly=True,
        help='Name of the KYC applicant'
    )
    
    partner_email = fields.Char(
        string='Applicant Email',
        related='kyc_application_id.email',
        readonly=True,
        help='Email of the applicant'
    )
    
    kyc_state = fields.Selection(
        string='KYC State',
        related='kyc_application_id.state',
        readonly=True,
        help='Current state of the KYC application'
    )
    
    age = fields.Integer(
        string='Applicant Age',
        related='kyc_application_id.age',
        readonly=True,
        help='Age of the applicant'
    )
    
    days_in_review = fields.Integer(
        string='Days in Review',
        compute='_compute_days_in_review',
        help='Number of days application has been under review'
    )
    
    review_completion_percentage = fields.Integer(
        string='Review Completion %',
        compute='_compute_review_completion',
        help='Percentage of review steps completed'
    )
    
    # ==================== COMPUTED METHODS ====================
    
    @api.depends('risk_score')
    def _compute_risk_level(self):
        """Determine risk level based on risk score"""
        for record in self:
            if record.risk_score < 30:
                record.risk_level = 'low'
            elif record.risk_score < 70:
                record.risk_level = 'medium'
            else:
                record.risk_level = 'high'
    
    @api.depends('review_start_date', 'review_end_date')
    def _compute_days_in_review(self):
        """Calculate days in review"""
        from datetime import datetime
        for record in self:
            if record.review_start_date:
                end_date = record.review_end_date or datetime.now()
                days = (end_date - record.review_start_date).days
                record.days_in_review = max(days, 0)
            else:
                record.days_in_review = 0
    
    @api.depends(
        'documents_complete',
        'documents_verified',
        'pep_check_performed',
        'sanctions_check_performed',
        'source_of_funds_verified',
        'source_of_wealth_verified',
        'signature_verified',
        'consent_verified',
        'risk_score',
    )
    def _compute_review_completion(self):
        """Calculate review completion percentage"""
        for record in self:
            completed_steps = sum([
                record.documents_complete,
                record.documents_verified,
                record.pep_check_performed,
                record.sanctions_check_performed,
                record.source_of_funds_verified,
                record.source_of_wealth_verified,
                record.signature_verified,
                record.consent_verified,
            ])
            record.review_completion_percentage = int((completed_steps / 8) * 100)
    
    # ==================== STATE TRANSITIONS ====================
    
    def action_start_review(self):
        """Start the approval review process"""
        for record in self:
            if record.status != 'pending':
                raise UserError(_('Only pending approvals can be started.'))
            
            record.write({
                'status': 'in_progress',
                'review_start_date': fields.Datetime.now(),
            })
            
            record.message_post(
                body=_('Approval review started by %s') % self.env.user.name,
                message_type='notification'
            )
    
    def action_approve_kyc(self):
        """Approve the KYC application"""
        for record in self:
            # Validate all checks are complete
            if not record.documents_verified:
                raise UserError(_('Documents must be verified before approval.'))
            
            if not record.pep_check_performed:
                raise UserError(_('PEP check must be performed before approval.'))
            
            if not record.sanctions_check_performed:
                raise UserError(_('Sanctions check must be performed before approval.'))

            if not record.source_of_funds_verified:
                raise UserError(_('Source of funds must be verified before approval.'))

            if not record.source_of_wealth_verified:
                raise UserError(_('Source of wealth must be verified before approval.'))

            if not record.signature_verified:
                raise UserError(_('Applicant signature must be verified before approval.'))

            if not record.consent_verified:
                raise UserError(_('Applicant consents must be verified before approval.'))
            
            # Check for high-risk items
            if record.risk_level == 'high' and not record.escalated_to_id:
                raise UserError(
                    _('High-risk applications must be escalated for approval.')
                )
            
            record.write({
                'status': 'approved',
                'approval_date': fields.Datetime.now(),
                'review_end_date': fields.Datetime.now(),
                'approved_by_id': self.env.user.id,
            })
            
            # Update KYC application state
            record.kyc_application_id.action_approve()
            
            record.message_post(
                body=_('KYC application approved by %s') % self.env.user.name,
                message_type='notification'
            )
            
            # Send approval notification
            record._notify_approval()
    
    def action_request_clarification(self):
        """Request clarification from applicant"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request Clarification'),
            'res_model': 'kyc.clarification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id},
        }
    
    def action_reject_kyc(self):
        """Reject the KYC application"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject KYC Application'),
            'res_model': 'kyc.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
                'default_kyc_id': self.kyc_application_id.id,
            },
        }

    def action_reset_approval(self):
        """Reset an approved or rejected approval record back to In Progress for re-review.

        Only KYC Admins can perform this action. Clears approval/rejection data and
        also resets the linked kyc.application back to pending_review so it can be
        re-processed.
        """
        for record in self:
            if record.status not in ('approved', 'rejected'):
                raise UserError(_('Only approved or rejected approvals can be reset for re-review.'))
            record.write({
                'status': 'in_progress',
                'approved_by_id': False,
                'approval_date': False,
                'rejection_date': False,
                'rejected_by_id': False,
                'rejection_reason': False,
                'rejection_suggestions': False,
            })
            if record.kyc_application_id and record.kyc_application_id.state in ('approved', 'rejected'):
                record.kyc_application_id.write({'state': 'pending_review'})
                record.kyc_application_id.message_post(
                    body=_('KYC application reset to Pending Review by %s for re-assessment.') % self.env.user.name,
                    message_type='notification',
                )
            record.message_post(
                body=_('Approval reset to In Progress by %s for re-review.') % self.env.user.name,
                message_type='notification',
            )
        return True

    def action_escalate(self):
        """Escalate to senior officer"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Escalate Approval'),
            'res_model': 'kyc.escalation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id},
        }
    
    # ==================== HELPER METHODS ====================
    
    def _notify_approval(self, attachment_ids=None):
        """Send internal notification to approver officer.
        
        :param attachment_ids: optional list of ir.attachment IDs to include
        """
        template = self.env.ref(
            'kyc_management.email_template_kyc_approval_notification',
            raise_if_not_found=False
        )
        if template:
            email_values = {}
            if attachment_ids:
                email_values['attachment_ids'] = attachment_ids
            template.send_mail(self.id, force_send=True, email_values=email_values)
    
    def _notify_rejection(self):
        """Send internal notification for rejection"""
        template = self.env.ref(
            'kyc_management.email_template_kyc_rejection_notification',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
    
    def _notify_clarification_request(self):
        """Send clarification request notification to applicant"""
        template = self.env.ref(
            'kyc_management.email_template_kyc_clarification_request',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)
    
    # ==================== OVERRIDE METHODS ====================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate and set defaults"""
        for vals in vals_list:
            # Check if approval already exists for this KYC
            existing = self.search([
                ('kyc_application_id', '=', vals.get('kyc_application_id')),
                ('status', '!=', 'rejected'),
            ])
            if existing:
                raise ValidationError(
                    _('An active approval workflow already exists for this KYC.')
                )
        
        return super().create(vals_list)
    
    def unlink(self):
        """Prevent deletion of completed approvals"""
        for record in self:
            if record.status in ('approved', 'rejected'):
                raise UserError(
                    _('Cannot delete completed approval workflows.')
                )
        return super().unlink()
    
    # ==================== CRON METHODS ====================
    
    @api.model
    def _remind_overdue_clarifications(self):
        """Cron: Remind applicants who haven't responded to clarification requests within 7 days"""
        from datetime import datetime, timedelta
        threshold = fields.Datetime.now() - timedelta(days=7)
        overdue = self.search([
            ('status', '=', 'needs_clarification'),
            ('clarification_requested', '=', True),
            ('clarification_request_date', '<=', threshold),
            ('clarification_response', '=', False),
        ])
        for approval in overdue:
            approval.kyc_application_id.message_post(
                body=_(
                    'Overdue Clarification: The applicant has not responded to the '
                    'clarification request sent on %s. Please follow up.'
                ) % (approval.clarification_request_date.strftime('%d %B %Y') if approval.clarification_request_date else 'N/A'),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
            # Re-send the clarification email
            approval._notify_clarification_request()
        _logger.info('KYC overdue clarification reminders sent for %d approvals.', len(overdue))
    
    @api.model
    def _remind_high_risk_escalations(self):
        """Cron: Weekly reminder for high-risk cases that require escalation but are unresolved"""
        unresolved = self.search([
            ('requires_escalation', '=', True),
            ('status', 'in', ('pending', 'in_progress', 'needs_clarification')),
            ('risk_level', '=', 'high'),
        ])
        for approval in unresolved:
            target = approval.escalated_to_id or approval.approver_id
            if target:
                approval.kyc_application_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=target.id,
                    summary=_('High-Risk KYC Escalation Reminder — %s') % approval.kyc_application_id.kyc_id,
                    note=_('This high-risk KYC case is still unresolved. Please review immediately.'),
                )
        _logger.info('KYC high-risk escalation reminders sent for %d cases.', len(unresolved))
