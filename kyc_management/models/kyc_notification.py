# -*- coding: utf-8 -*-
"""
KYC Notification Model
Manages notifications and communications for KYC applications
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KYCNotification(models.Model):
    """
    KYC Notification Model
    
    Tracks all notifications and communications related to KYC applications.
    Supports email notifications, in-app notifications, and scheduled reminders.
    """
    
    _name = 'kyc.notification'
    _description = 'KYC Notification'
    _inherit = ['mail.thread']
    _order = 'create_date DESC'
    
    # ==================== BASIC INFORMATION ====================
    
    kyc_application_id = fields.Many2one(
        'kyc.application',
        string='KYC Application',
        required=True,
        ondelete='cascade',
        help='Link to the KYC application'
    )
    
    notification_type = fields.Selection([
        ('submission_received', 'Submission Received'),
        ('documents_requested', 'Documents Requested'),
        ('clarification_requested', 'Clarification Requested'),
        ('under_review', 'Under Review'),
        ('review_in_progress', 'Review In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('resubmission_requested', 'Resubmission Requested'),
        ('reminder', 'Reminder'),
        ('status_update', 'Status Update'),
    ], string='Notification Type', required=True,
       help='Type of notification')
    
    notification_category = fields.Selection([
        ('approval_workflow', 'Approval Workflow'),
        ('document_request', 'Document Request'),
        ('reminder', 'Reminder'),
        ('system_notification', 'System Notification'),
        ('compliance_alert', 'Compliance Alert'),
    ], string='Category', required=True,
       help='Notification category for filtering')
    
    # ==================== RECIPIENTS ====================
    
    recipient_type = fields.Selection([
        ('applicant', 'Applicant'),
        ('approver', 'Approver'),
        ('admin', 'Administrator'),
        ('compliance_team', 'Compliance Team'),
    ], string='Recipient Type', required=True,
       help='Who should receive this notification')
    
    recipient_user_id = fields.Many2one(
        'res.users',
        string='Recipient User',
        help='Specific user to receive notification'
    )
    
    recipient_partner_id = fields.Many2one(
        'res.partner',
        string='Recipient Contact',
        help='Specific contact to receive notification'
    )
    
    recipient_email = fields.Char(
        string='Recipient Email',
        required=True,
        help='Email address where notification will be sent'
    )
    
    # ==================== CONTENT ====================
    
    subject = fields.Char(
        string='Subject',
        required=True,
        help='Email subject line'
    )
    
    body = fields.Html(
        string='Message Body',
        help='Notification message content'
    )
    
    summary = fields.Text(
        string='Summary',
        help='Brief summary of notification'
    )
    
    # ==================== COMMUNICATION CHANNELS ====================
    
    # Email
    email_enabled = fields.Boolean(
        string='Send via Email',
        default=True,
        help='Whether to send email notification'
    )
    
    email_sent = fields.Boolean(
        string='Email Sent',
        default=False,
        readonly=True,
        help='Has email been successfully sent?'
    )
    
    email_sent_date = fields.Datetime(
        string='Email Sent Date',
        readonly=True,
        help='When email was sent'
    )
    
    email_bounce = fields.Boolean(
        string='Email Bounced',
        default=False,
        help='Did email bounce?'
    )
    
    # SMS (if enabled)
    sms_enabled = fields.Boolean(
        string='Send via SMS',
        default=False,
        help='Whether to send SMS notification'
    )
    
    sms_sent = fields.Boolean(
        string='SMS Sent',
        default=False,
        readonly=True,
        help='Has SMS been sent?'
    )
    
    sms_sent_date = fields.Datetime(
        string='SMS Sent Date',
        readonly=True,
        help='When SMS was sent'
    )
    
    phone_number = fields.Char(
        string='SMS Phone Number',
        help='Phone number for SMS delivery'
    )
    
    # In-App Notification
    inapp_enabled = fields.Boolean(
        string='Show In-App Notification',
        default=True,
        help='Whether to show in-app notification'
    )
    
    inapp_created = fields.Boolean(
        string='In-App Notification Created',
        default=False,
        readonly=True,
        help='Has in-app notification been created?'
    )
    
    inapp_read = fields.Boolean(
        string='In-App Notification Read',
        default=False,
        help='Has user read the in-app notification?'
    )
    
    inapp_read_date = fields.Datetime(
        string='In-App Read Date',
        readonly=True,
        help='When user read the notification'
    )
    
    # ==================== SCHEDULING ====================
    
    schedule_send = fields.Boolean(
        string='Schedule Send',
        default=False,
        help='Send notification at a specific time'
    )
    
    send_date = fields.Datetime(
        string='Send Date/Time',
        help='When to send this notification'
    )
    
    is_reminder = fields.Boolean(
        string='Is Reminder',
        default=False,
        help='Is this a reminder notification?'
    )
    
    reminder_days_before = fields.Integer(
        string='Remind X Days Before',
        default=0,
        help='Send reminder N days before the event'
    )
    
    reminder_date = fields.Datetime(
        string='Reminder Date',
        compute='_compute_reminder_date',
        help='Calculated reminder date'
    )
    
    # ==================== STATUS & TRACKING ====================
    
    status = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('read', 'Read'),
        ('skipped', 'Skipped'),
    ], string='Status', default='draft', required=True,
       help='Notification status', tracking=True)
    
    send_attempts = fields.Integer(
        string='Send Attempts',
        default=0,
        help='Number of times sending has been attempted'
    )
    
    max_send_attempts = fields.Integer(
        string='Max Send Attempts',
        default=3,
        help='Maximum number of send attempts before giving up'
    )
    
    last_error = fields.Text(
        string='Last Error',
        help='Error message from last failed attempt'
    )
    
    # ==================== PRIORITY & IMPORTANCE ====================
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='normal',
       help='Notification priority level')
    
    is_critical = fields.Boolean(
        string='Critical',
        default=False,
        help='Is this a critical notification?'
    )
    
    requires_acknowledgment = fields.Boolean(
        string='Requires Acknowledgment',
        default=False,
        help='Does recipient need to acknowledge receipt?'
    )
    
    acknowledged_by_id = fields.Many2one(
        'res.users',
        string='Acknowledged By',
        readonly=True,
        help='User who acknowledged the notification'
    )
    
    acknowledged_date = fields.Datetime(
        string='Acknowledged Date',
        readonly=True,
        help='When notification was acknowledged'
    )
    
    # ==================== TEMPLATE INFORMATION ====================
    
    email_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        help='Email template used for this notification'
    )
    
    sms_template_id = fields.Many2one(
        'sms.template',
        string='SMS Template',
        help='SMS template used for this notification'
    )
    
    # ==================== ATTACHMENTS ====================
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'kyc_notification_attachment_rel',
        'notification_id',
        'attachment_id',
        string='Attachments',
        help='Documents attached to notification'
    )
    
    # ==================== AUDIT TRAIL ====================
    
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        readonly=True,
        default=lambda self: self.env.user,
        help='User who created this notification'
    )
    
    sent_by_id = fields.Many2one(
        'res.users',
        string='Sent By',
        readonly=True,
        help='User who triggered sending (if manual)'
    )
    
    # ==================== SYSTEM FIELDS ====================
    
    kyc_state = fields.Selection(
        string='KYC State',
        related='kyc_application_id.state',
        readonly=True,
        help='Current state of KYC application'
    )
    
    partner_name = fields.Char(
        string='Applicant Name',
        related='kyc_application_id.partner_id.name',
        readonly=True,
        help='Name of KYC applicant'
    )
    
    # ==================== COMPUTED FIELDS ====================
    
    time_until_send = fields.Char(
        string='Time Until Send',
        compute='_compute_time_until_send',
        help='How long until notification is sent'
    )
    
    delivery_status = fields.Char(
        string='Delivery Status Summary',
        compute='_compute_delivery_status',
        help='Summary of delivery status across channels'
    )
    
    has_been_sent = fields.Boolean(
        string='Has Been Sent',
        compute='_compute_has_been_sent',
        help='Whether any attempt to send has been made'
    )
    
    # ==================== COMPUTED METHODS ====================
    
    @api.depends('reminder_days_before', 'kyc_application_id.submitted_date')
    def _compute_reminder_date(self):
        """Compute reminder date based on submission date and days before"""
        from datetime import timedelta
        for record in self:
            if record.kyc_application_id.submitted_date and record.reminder_days_before:
                base_date = record.kyc_application_id.submitted_date
                record.reminder_date = base_date + timedelta(days=record.reminder_days_before)
            else:
                record.reminder_date = False
    
    @api.depends('send_date')
    def _compute_time_until_send(self):
        """Calculate time remaining until send"""
        from datetime import datetime
        for record in self:
            if record.send_date:
                now = datetime.now()
                delta = record.send_date - now
                if delta.total_seconds() > 0:
                    days = delta.days
                    hours = (delta.seconds // 3600)
                    if days > 0:
                        record.time_until_send = f'{days}d {hours}h'
                    else:
                        record.time_until_send = f'{hours}h'
                else:
                    record.time_until_send = 'Due Now'
            else:
                record.time_until_send = 'Not Scheduled'
    
    @api.depends('email_sent', 'sms_sent', 'inapp_created')
    def _compute_delivery_status(self):
        """Summary of delivery status"""
        for record in self:
            statuses = []
            if record.email_enabled:
                statuses.append(f"Email: {'✓' if record.email_sent else '✗'}")
            if record.sms_enabled:
                statuses.append(f"SMS: {'✓' if record.sms_sent else '✗'}")
            if record.inapp_enabled:
                statuses.append(f"In-App: {'✓' if record.inapp_created else '✗'}")
            record.delivery_status = ' | '.join(statuses) if statuses else 'No channels enabled'
    
    @api.depends('email_sent', 'sms_sent')
    def _compute_has_been_sent(self):
        """Check if any send attempt has been made"""
        for record in self:
            record.has_been_sent = record.email_sent or record.sms_sent or record.status == 'sent'
    
    # ==================== ACTION METHODS ====================
    
    def action_send_email(self):
        """Manually trigger email sending"""
        for record in self:
            if not record.email_enabled:
                raise ValidationError(_('Email is not enabled for this notification.'))
            
            try:
                # Get mail template
                template = record.email_template_id
                if not template:
                    _logger.warning(f'No email template for notification {record.id}')
                    record.write({'last_error': 'No email template configured'})
                    return
                
                # Send email
                template.send_mail(record.kyc_application_id.id)
                
                record.write({
                    'email_sent': True,
                    'email_sent_date': fields.Datetime.now(),
                    'send_attempts': record.send_attempts + 1,
                    'status': 'sent' if record.email_sent else record.status,
                    'sent_by_id': self.env.user.id,
                })
                
                record.message_post(
                    body=_('Email notification sent by %s') % self.env.user.name,
                    message_type='notification'
                )
                
            except Exception as e:
                record.write({
                    'send_attempts': record.send_attempts + 1,
                    'last_error': str(e),
                    'status': 'failed' if record.send_attempts >= record.max_send_attempts else 'draft',
                })
                _logger.error(f'Failed to send notification {record.id}: {str(e)}')
    
    def action_send_sms(self):
        """Manually trigger SMS sending"""
        for record in self:
            if not record.sms_enabled:
                raise ValidationError(_('SMS is not enabled for this notification.'))
            
            if not record.phone_number:
                raise ValidationError(_('No phone number provided for SMS.'))
            
            # SMS sending logic would go here
            record.write({
                'sms_sent': True,
                'sms_sent_date': fields.Datetime.now(),
                'sent_by_id': self.env.user.id,
            })
    
    def action_schedule(self):
        """Schedule notification for sending"""
        for record in self:
            if not record.send_date:
                raise ValidationError(_('Please select a send date/time.'))
            
            record.write({'status': 'scheduled'})
            
            record.message_post(
                body=_('Notification scheduled for %s') % record.send_date,
                message_type='notification'
            )
    
    def action_mark_read(self):
        """Mark notification as read"""
        for record in self:
            record.write({
                'inapp_read': True,
                'inapp_read_date': fields.Datetime.now(),
                'status': 'read' if record.email_sent or record.sms_sent else 'draft',
            })
    
    def action_acknowledge(self):
        """Acknowledge critical notification"""
        for record in self:
            if not record.requires_acknowledgment:
                raise ValidationError(_('This notification does not require acknowledgment.'))
            
            record.write({
                'acknowledged_by_id': self.env.user.id,
                'acknowledged_date': fields.Datetime.now(),
            })
            
            record.message_post(
                body=_('Notification acknowledged by %s') % self.env.user.name,
                message_type='notification'
            )
    
    def action_retry_send(self):
        """Retry sending failed notification"""
        for record in self:
            if record.status != 'failed':
                raise ValidationError(_('Only failed notifications can be retried.'))
            
            if record.send_attempts >= record.max_send_attempts:
                raise ValidationError(
                    _('Maximum send attempts (%d) reached.') % record.max_send_attempts
                )
            
            if record.email_enabled:
                record.action_send_email()
            
            if record.sms_enabled:
                record.action_send_sms()
    
    # ==================== OVERRIDE METHODS ====================
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create notification with defaults"""
        for vals in vals_list:
            # Auto-fill recipient email if not provided
            if not vals.get('recipient_email'):
                kyc_id = vals.get('kyc_application_id')
                if kyc_id:
                    kyc = self.env['kyc.application'].browse(kyc_id)
                    vals['recipient_email'] = kyc.email
        
        return super().create(vals_list)
    
    def write(self, vals):
        """Override write to prevent editing of sent notifications"""
        for record in self:
            if record.status == 'sent' and 'status' not in vals:
                raise ValidationError(_('Cannot edit sent notifications.'))
        
        return super().write(vals)
    
    # ==================== CRON METHODS ====================
    
    @api.model
    def _retry_failed_notifications(self):
        """Cron: Retry sending failed notifications that haven't exceeded max attempts"""
        failed = self.search([
            ('status', '=', 'failed'),
            ('send_attempts', '<', 3),  # Default max attempts
        ])
        retried = 0
        for notification in failed:
            try:
                if notification.send_attempts < notification.max_send_attempts:
                    if notification.email_enabled:
                        notification.action_send_email()
                    if notification.sms_enabled:
                        notification.action_send_sms()
                    retried += 1
            except Exception as e:
                _logger.warning(
                    'KYC notification retry failed for %s: %s',
                    notification.display_name, str(e),
                )
        _logger.info(
            'KYC notification retry: %d of %d failed notifications retried.',
            retried, len(failed),
        )


class KYCNotificationType(models.Model):
    """
    KYC Notification Type Configuration
    Defines templates and rules for each type of notification
    """
    
    _name = 'kyc.notification.type'
    _description = 'KYC Notification Type Configuration'
    _order = 'name'
    
    name = fields.Char(
        string='Notification Type',
        required=True,
        help='Name of the notification type'
    )
    
    notification_type = fields.Selection([
        ('submission_received', 'Submission Received'),
        ('documents_requested', 'Documents Requested'),
        ('clarification_requested', 'Clarification Requested'),
        ('under_review', 'Under Review'),
        ('review_in_progress', 'Review In Progress'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('resubmission_requested', 'Resubmission Requested'),
        ('reminder', 'Reminder'),
        ('status_update', 'Status Update'),
    ], string='Type Code', required=True)
    
    email_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        help='Default email template for this type'
    )
    
    sms_template_id = fields.Many2one(
        'sms.template',
        string='SMS Template',
        help='Default SMS template for this type'
    )
    
    is_enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Is this notification type active?'
    )
    
    auto_send = fields.Boolean(
        string='Auto Send',
        default=True,
        help='Automatically send when triggered'
    )
    
    delay_hours = fields.Integer(
        string='Delay (hours)',
        default=0,
        help='Delay before sending (in hours)'
    )
    
    remind_every_days = fields.Integer(
        string='Remind Every (days)',
        default=0,
        help='Re-send reminder every N days (0 = no repeat)'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of when this notification is sent'
    )
