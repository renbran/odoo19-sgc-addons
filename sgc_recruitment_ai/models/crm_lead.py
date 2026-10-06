from odoo import models, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('_research_email_sent'):
            return res
        if 'stage_id' not in vals and 'tag_ids' not in vals:
            return res
        template = self.env['mail.template'].browse(89)
        if not template.exists():
            return res
        for lead in self:
            if lead.stage_id.id == 10 and 19 in lead.tag_ids.ids:
                template.with_context(
                    _research_email_sent=True,
                ).send_mail(lead.id, force_send=True)
        return res
