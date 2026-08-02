from odoo import api, models


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    @api.model
    def default_get(self, fields_list):
        """The stock _compute_email_layout_xmlid never actually runs here:
        Odoo's ORM uses default_get()'s context-provided value for a field
        directly at create() time and does not invoke that field's compute
        method when an explicit default already exists for it - confirmed
        empirically (overriding the compute method alone had no effect).
        The real point of failure is this default_get() call itself: it
        resolves default_email_layout_xmlid from context (e.g.
        action_quotation_send()'s hardcoded
        mail.mail_notification_layout_with_responsible_signature)
        regardless of what the also-defaulted template_id's own
        email_layout_xmlid says. Correct it here, once, for every calling
        action, rather than patching action_quotation_send() /
        action_send_and_print() / etc. individually across multiple core
        models.
        """
        defaults = super().default_get(fields_list)
        template_id = defaults.get('template_id')
        if template_id and 'email_layout_xmlid' in fields_list:
            template = self.env['mail.template'].browse(template_id)
            if not template.email_layout_xmlid:
                defaults['email_layout_xmlid'] = False
        return defaults
