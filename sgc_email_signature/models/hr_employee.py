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
        phone_block = ''
        if phone:
            phone_block = (
                '<a href="%s" style="color:#1C2430;text-decoration:none;">%s</a>'
                '<span style="color:#B79554;">&nbsp;&nbsp;|&nbsp;&nbsp;</span>'
            ) % (esc(self._compute_sgc_phone_href(phone)), esc(phone))

        email_block = ''
        if email:
            email_block = (
                '<a href="mailto:%s" style="color:#1C2430;text-decoration:none;">%s</a>'
            ) % (esc(email), esc(email))

        address_label = 'Dubai,&nbsp;UAE'
        for part in (address or '').split(', '):
            p = part.strip()
            if p.lower() in ('united arab emirates', 'uae', 'dubai'):
                address_label = 'Dubai,&nbsp;UAE'
            elif p and p.lower() not in ('united arab emirates',):
                address_label = '%s,&nbsp;UAE' % esc(p) if p.lower() == 'dubai' else address_label

        img = _sig_img_data_uris()

        icons = ''.join(
            '<a href="%s" target="_blank" style="text-decoration:none;"><img src="%s" '
            'width="14" height="14" alt="%s" style="border:0;margin-right:7px;vertical-align:middle;"></a>' % (
                url, img[key], label)
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
            '<table cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;background-color:#F7F4EE;max-width:300px;'
            "font-family:'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif;\">"
            '<tr><td style="height:1px;line-height:1px;font-size:0;background-color:#B79554;">&nbsp;</td></tr>'
            '<tr><td style="padding:6px 10px 4px 10px;">'
            '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>'
            '<td valign="middle" width="46" style="padding-right:8px;">'
            '<a href="%(web)s" target="_blank"><img src="%(logo)s" '
            'width="40" alt="SGC TECH AI" style="display:block;width:40px;max-width:40px;height:auto;border:0;"></a>'
            '</td>'
            '<td valign="middle" style="border-left:1px solid #D9C08A;padding-left:8px;">'
            '<div style="font-family:%(font)s;font-size:12px;line-height:15px;font-weight:700;color:#0F213D;'
            'letter-spacing:-0.2px;">%(name)s</div>'
            '<div style="margin-top:0;font-size:7px;line-height:9px;font-weight:600;color:#B79554;'
            'text-transform:uppercase;letter-spacing:1px;">%(job)s</div>'
            '<div style="margin-top:0;font-size:7px;line-height:9px;font-weight:600;color:#1C2430;'
            'letter-spacing:0.8px;text-transform:uppercase;">%(company)s</div>'
            '<div style="margin-top:2px;font-size:9px;line-height:12px;color:#5F6775;">'
            '%(phone)s%(email)s'
            '</div>'
            '<div style="margin-top:1px;font-size:9px;line-height:12px;color:#5F6775;">'
            '<a href="%(web)s" target="_blank" style="color:#1C2430;text-decoration:none;">%(web)s</a>'
            '<span style="color:#B79554;">&nbsp;|&nbsp;</span>'
            '<span style="color:#5F6775;">Dubai, UAE</span>'
            '</div>'
            '<div style="margin-top:3px;">%(icons)s</div>'
            '</td>'
            '</tr></table>'
            '</td></tr>'
            '<tr><td style="background:#0F213D;padding:3px 10px;'
            "font-family:'IBM Plex Serif',Georgia,serif;font-size:8px;line-height:10px;color:#F7F4EE;"
            'font-style:italic;">Finance.System.Technology</td></tr>'
            '</table>'
        ) % {
            'font': "'IBM Plex Serif',Georgia,'Times New Roman',serif",
            'name': esc(name),
            'job': esc(job_title),
            'company': esc(company_name),
            'phone': phone_block,
            'email': email_block,
            'address': address_label,
            'web': esc(website.rstrip('/')),
            'icons': icons,
            'logo': img['logo'],
            'icon_linkedin': img['icon_linkedin'],
            'icon_facebook': img['icon_facebook'],
            'icon_instagram': img['icon_instagram'],
            'icon_youtube': img['icon_youtube'],
            'icon_twitter': img['icon_twitter'],
        }