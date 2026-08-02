from odoo import api, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.depends('template_id')
    def _compute_email_layout_xmlid(self):
        """Stock logic only overrides email_layout_xmlid when the selected
        template's own value is truthy - an explicitly empty value (this
        brand's fully self-contained templates, e.g. the SGC quotation/
        invoice/receipt/proforma bodies) is treated as "no opinion" and
        whatever generic default the calling action's context set (e.g.
        action_quotation_send()'s hardcoded
        mail.mail_notification_layout_with_responsible_signature) silently
        survives instead. Confirmed empirically: composing from a template
        with email_layout_xmlid='' still resolved to the stock layout.
        Correct that one gap without touching any other template's
        behaviour - stock templates with a real layout value are untouched.
        """
        super()._compute_email_layout_xmlid()
        for composer in self:
            if composer.template_id and not composer.template_id.email_layout_xmlid:
                composer.email_layout_xmlid = False
