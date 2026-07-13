from odoo import models, tools


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def _send(self, **kwargs):
        blocked = self.env['ir.config_parameter'].sudo().get_param(
            'mail.blocked_domains', '')
        blocked_domains = set(
            d.strip().lower() for d in blocked.split(',') if d.strip())
        if not blocked_domains:
            return super()._send(**kwargs)

        to_block = self.env['mail.mail']
        for mail in self:
            recipients = tools.email_split(mail.email_to or '')
            for addr in recipients:
                domain = addr.split('@')[-1].lower()
                for bd in blocked_domains:
                    if domain == bd or domain.endswith('.' + bd):
                        to_block |= mail
                        break

        if to_block:
            to_block.write({
                'state': 'exception',
                'failure_reason': 'Blocked domain per mail.blocked_domains config',
                'failure_type': 'mail_domain_blocked',
            })

        remaining = self - to_block
        if remaining:
            return super(MailMail, remaining)._send(**kwargs)
        return True
