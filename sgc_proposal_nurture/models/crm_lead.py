from odoo import models, fields


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # Dedicated clock, separate from the built-in date_last_stage_update —
    # that field resets on every stage move, so a lead bouncing
    # Proposal -> Negotiation -> Proposal would restart the 3-day clock
    # and get flagged twice.
    x_proposal_entered_on = fields.Datetime(string='Proposal Stage Entered On')

    x_nurture_state = fields.Selection([
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('stopped', 'Stopped'),
    ], string='Nurture State')

    x_nurture_flagged_on = fields.Datetime(string='Nurture Flagged On')
