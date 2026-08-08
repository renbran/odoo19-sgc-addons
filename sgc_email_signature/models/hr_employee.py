import base64
import html
import os
from functools import lru_cache

from odoo import api, models



@lru_cache(maxsize=1)
def _sig_img_data_uris():
    """Base64 data-URIs of the signature assets (logo + social icons),
    embedded so the signature renders in clients that block remote images."""
    base = os.path.join(os.path.dirname(__file__), '..', 'static', 'src', 'img')
    uris = {}
    for name in ('logo', 'icon_linkedin', 'icon_facebook', 'icon_instagram',
                 'icon_youtube', 'icon_twitter', 'icon_tiktok'):
        path = os.path.join(base, '%s.png' % name)
        with open(path, 'rb') as f:
            uris[name] = 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')
    return uris


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ------------------------------------------------------------------
    # Lifecycle hooks: keep the linked user's email signature in sync
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._update_email_signature()
        return records

    def write(self, vals):
        res = super().write(vals)
        tracked = {'name', 'work_email', 'mobile_phone', 'work_phone', 'address_id', 'user_id', 'company_id', 'job_title'}
        if tracked.intersection(vals):
            self._update_email_signature()
        return res

    def _update_email_signature(self):
        """(Re)generate the branded HTML signature for the linked internal user."""
        for employee in self:
            user = employee.user_id
            if not user and employee.work_email:
                user = self.env['res.users'].search(
                    [('login', '=ilike', employee.work_email), ('share', '=', False)], limit=1)
            if user:
                user.signature = employee._compute_sgc_signature()

    def regenerate_all_signatures(self):
        """Server-action entry point: refresh signatures for every employee
        that is linked to an internal user."""
        employees = self.search([('user_id', '!=', False)])
        employees._update_email_signature()
        return True

    # ------------------------------------------------------------------
    # Signature builder
    # ------------------------------------------------------------------

    def _compute_sig_company_values(self):
        company = self.company_id
        partner = company.partner_id
        state_name = partner.state_id.name if partner.state_id else False
        country_name = partner.country_id.name if partner.country_id else False
        address_parts = [partner.street, partner.street2]
        if partner.city and (not state_name or partner.city.upper() != state_name.upper()):
            address_parts.append(partner.city)
        if state_name:
            address_parts.append(state_name)
        if country_name:
            address_parts.append(country_name)
        return {
            'company_name': str(company.name or 'SGC TECH AI').split(' (')[0],
            'website': partner.website or 'https://sgctech.ai',
            'address': ', '.join([p for p in address_parts if p]),
        }

    def _compute_sgc_phone(self):
        """Preferred: mobile, then work phone, then partner phone."""
        return self.mobile_phone or self.work_phone or (self.work_contact_id.phone or False)

    @staticmethod
    def _compute_sgc_phone_href(phone):
        digits = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
        return 'tel:%s' % digits

    def _compute_sgc_signature(self):
        """Public helper: compute the HTML signature from the employee's current data."""
        self.ensure_one()

        def esc(v):
            return html.escape(v or '', quote=True)

        company = self._compute_sig_company_values()
        job_title = (self.job_title or '').strip()
        name = (self.name or '').strip()
        phone = self._compute_sgc_phone()
        email = (self.work_email or '').strip()
        website = company['website']
        address = company['address']
        company_name = company['company_name']
        contact_parts = []
        if phone:
            contact_parts.append(
                '<span style="color:#A8822B;font-weight:600;">M</span>'
                '&nbsp;&nbsp;<a href="%s" style="color:#1C2430;text-decoration:none;">%s</a>'
                % (esc(self._compute_sgc_phone_href(phone)), esc(phone))
            )
        if email:
            contact_parts.append(
                '<span style="color:#A8822B;font-weight:600;">E</span>'
                '&nbsp;&nbsp;<a href="mailto:%s" style="color:#1C2430;text-decoration:none;">%s</a>'
                % (esc(email), esc(email))
            )
        contact_parts.append(
            '<span style="color:#A8822B;font-weight:600;">W</span>'
            '&nbsp;&nbsp;<a href="%(web)s" target="_blank" style="color:#1C2430;text-decoration:none;">'
            '%(web)s</a>' % {'web': esc(website.rstrip('/'))}
        )
        contact_line = '&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;'.join(contact_parts)

        address_line = ''
        if address:
            address_line = (
                '<div style="font-size:10px;line-height:16px;color:#5F6673;">%(address)s</div>'
                % {'address': esc(address)}
            )

        img = _sig_img_data_uris()

        icons = ''.join(
            '<a href="%s" target="_blank" style="text-decoration:none;"><img src="%s" '
            'width="16" height="16" alt="%s" style="display:inline-block;border:0;margin-right:9px;'
            'vertical-align:middle;"></a>' % (url, img[key], label)
            for key, url, label in (
                ('icon_linkedin', 'https://www.linkedin.com/company/sgctechai/', 'LinkedIn'),
                ('icon_facebook', 'https://www.facebook.com/sgctechai', 'Facebook'),
                ('icon_instagram', 'https://www.instagram.com/sgctech.ai/', 'Instagram'),
                ('icon_youtube', 'https://www.youtube.com/@sgctechai', 'YouTube'),
                ('icon_twitter', 'https://x.com/sgctech_ai', 'X'),
                ('icon_tiktok', 'https://www.tiktok.com/@scholarixglobal', 'TikTok'),
            )
        )

        return (
            '<table cellpadding="0" cellspacing="0" border="0" role="presentation" '
            'style="border-collapse:collapse;width:600px;max-width:600px;background-color:#F7F4EE;'
            "font-family:'IBM Plex Sans','Segoe UI',Arial,sans-serif;\">"
            '<tr><td bgcolor="#B79554" style="height:2px;line-height:2px;font-size:0;background-color:#B79554;">'
            '&nbsp;</td></tr>'
            '<tr><td style="padding:16px 20px 14px 20px;">'
            '<table cellpadding="0" cellspacing="0" border="0" role="presentation" width="100%%" '
            'style="border-collapse:collapse;">'
            '<tr>'
            '<td width="112" valign="top" style="padding:2px 18px 0 0;">'
            '<a href="%(web)s" target="_blank"><img src="%(logo)s" width="100" alt="SGC TECH AI" '
            'style="display:block;width:100px;height:auto;border:0;"></a>'
            '</td>'
            '<td valign="top" style="border-left:1px solid #D9C08A;padding-left:16px;">'
            '<div style="font-family:%(font)s;font-size:19px;line-height:24px;font-weight:700;'
            'color:#0F2137;letter-spacing:-0.2px;">%(name)s</div>'
            '<div style="font-size:10px;line-height:16px;font-weight:600;color:#A8822B;'
            'text-transform:uppercase;letter-spacing:1.6px;">%(job)s</div>'
            '<div style="font-size:10px;line-height:16px;font-weight:600;color:#1C2430;'
            'letter-spacing:1.2px;text-transform:uppercase;">%(company)s</div>'
            '<div style="width:38px;height:2px;margin:5px 0 4px 0;background-color:#C9A86A;'
            'font-size:0;line-height:0;">&nbsp;</div>'
            '<div style="font-size:11px;line-height:20px;color:#5F6673;">%(contact)s</div>'
            '%(address)s'
            '<div style="font-size:0;line-height:0;margin-top:6px;">%(icons)s</div>'
            '</td>'
            '</tr>'
            '</table>'
            '</td></tr>'
            '<tr><td bgcolor="#0F2137" style="background-color:#0F2137;padding:6px 20px;'
            "font-family:'IBM Plex Serif',Georgia,serif;font-size:11px;line-height:14px;color:#F7F4EE;"
            'font-style:italic;">Finance.System.Technology</td></tr>'
            '<tr><td style="border-top:1px solid #E4DECF;padding:3px 20px 4px 20px;font-size:8px;'
            'line-height:11px;color:#959DA8;">CONFIDENTIAL — This message and any attachments are intended '
            'solely for the addressee. If received in error, please notify the sender and delete all copies.</td></tr>'
            '</table>'
        ) % {
            'font': "'IBM Plex Serif',Georgia,'Times New Roman',serif",
            'name': esc(name),
            'job': esc(job_title),
            'company': esc(company_name),
            'contact': contact_line,
            'address': address_line,
            'web': esc(website.rstrip('/')),
            'icons': icons,
            'logo': img['logo'],
        }