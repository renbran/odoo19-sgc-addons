from odoo import _, fields, models
from odoo.exceptions import UserError

# DB ids of the outreach templates on odoo19-sgc
TEMPLATE_BY_TYPE = {
    'sales': 88,      # SGC TECH AI - Sales Outreach (Operational Health Score)
    'research': 90,   # SGC TECH AI - Research Participation (AI Adoption Index)
}


class CrmOutreachWizard(models.TransientModel):
    _name = 'crm.outreach.wizard'
    _description = 'CRM Outreach Email Wizard'

    lead_id = fields.Many2one(
        'crm.lead', string='Lead', required=True, ondelete='cascade',
        default=lambda self: self.env.context.get('default_lead_id')
        or self.env.context.get('active_id'))
    email_type = fields.Selection(
        [('sales', 'Sales Deck — Operational Health Score'),
         ('research', 'Research — UAE AI & Tech Adoption Index')],
        string='Email Type', required=True, default='sales')

    def action_send(self):
        self.ensure_one()
        lead = self.lead_id
        if lead.outreach_mail_sent:
            raise UserError(_(
                "An outreach email was already sent for this lead. "
                "Only one outreach email per lead is allowed."))
        if not lead.email_from and not (lead.partner_id and lead.partner_id.email):
            raise UserError(_("No email address found on this lead."))
        template = self.env['mail.template'].browse(TEMPLATE_BY_TYPE[self.email_type])
        if not template.exists():
            raise UserError(_("Outreach mail template is missing."))
        # template email_from/reply_to render the assigned salesperson as sender
        template.send_mail(lead.id, force_send=False)
        lead.write({'outreach_mail_sent': True})
        label = dict(self._fields['email_type'].selection)[self.email_type]
        lead.message_post(body=_("Outreach email queued: %s", label))
        return {'type': 'ir.actions.act_window_close'}

    def action_skip(self):
        self.ensure_one()
        # mark as handled so the popup does not nag again on later stage moves
        self.lead_id.write({'outreach_mail_sent': True})
        self.lead_id.message_post(body=_("Outreach email skipped by user."))
        return {'type': 'ir.actions.act_window_close'}
