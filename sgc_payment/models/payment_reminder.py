from odoo import models, fields


class PaymentReminderManager(models.Model):
    _name = 'payment.reminder.manager'
    _description = 'Payment Reminder Manager'

    payment_id = fields.Many2one('account.payment', string='Payment', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', related='payment_id.partner_id', store=True)
    reminder_date = fields.Datetime(string='Reminder Date', default=fields.Datetime.now)
    reminder_type = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('system', 'System Notification'),
    ], string='Reminder Type', default='email')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ], string='State', default='pending')
    failure_reason = fields.Text(string='Failure Reason')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
