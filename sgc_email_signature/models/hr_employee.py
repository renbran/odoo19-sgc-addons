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
                '<tr><td valign="top" style="padding:1px 10px 1px 0;font-size:9px;font-weight:600;'
                'letter-spacing:1.2px;color:#B79554;">M</td>'
                '<td style="padding:1px 0;"><a href="%s" style="color:#1C2430;text-decoration:none;">%s</a></td></tr>'
            ) % (esc(self._compute_sgc_phone_href(phone)), esc(phone))

        email_block = ''
        if email:
            email_block = (
                '<tr><td valign="top" style="padding:1px 10px 1px 0;font-size:9px;font-weight:600;'
                'letter-spacing:1.2px;color:#B79554;">E</td>'
                '<td style="padding:1px 0;"><a href="mailto:%s" style="color:#1C2430;text-decoration:none;">%s</a></td></tr>'
            ) % (esc(email), esc(email))

        address_row = ''
        if address:
            address_row = (
                '<tr><td valign="top" style="padding:1px 10px 1px 0;font-size:9px;font-weight:600;'
                'letter-spacing:1.2px;color:#B79554;">A</td>'
                '<td style="padding:1px 0;color:#5F6775;">%s</td></tr>'
            ) % esc(address)

        img = _sig_img_data_uris()

        return (
            '<table cellpadding="0" cellspacing="0" border="0" '
            'style="border-collapse:collapse;background-color:#F7F4EE;max-width:480px;'
            "font-family:'IBM Plex Sans','Segoe UI',Helvetica,Arial,sans-serif;\">"
            '<tr><td style="height:3px;line-height:3px;font-size:0;background-color:#B79554;">&nbsp;</td></tr>'
            '<tr><td style="padding:16px 22px 12px 22px;">'
            '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;"><tr>'
            '<td valign="top" width="104" style="padding-right:16px;">'
'<a href="%(web)s" target="_blank"><img src="%(logo)s" '
            'width="96" alt="SGC TECH AI" style="display:block;width:96px;max-width:96px;height:auto;border:0;"></a>'
            '<div style="margin-top:8px;font-size:7px;letter-spacing:1.4px;color:#B79554;'
            "font-family:Consolas,'Courier New',monospace;\">25.2048&nbsp;N&nbsp;·&nbsp;55.2708&nbsp;E</div>"
            '</td>'
            '<td width="1" style="width:1px;background-color:#D9C08A;font-size:0;line-height:0;">&nbsp;</td>'
            '<td valign="top" style="padding-left:16px;">'
            '<div style="font-family:%(font)s;font-size:15px;line-height:18px;font-weight:700;color:#0F213D;'
            'letter-spacing:-0.2px;">%(name)s</div>'
            '<div style="margin-top:3px;font-size:8px;line-height:11px;font-weight:600;color:#B79554;'
            'text-transform:uppercase;letter-spacing:1.8px;">%(job)s</div>'
            '<div style="margin-top:2px;font-size:9px;line-height:12px;font-weight:600;color:#1C2430;'
            'letter-spacing:1.2px;text-transform:uppercase;">%(company)s</div>'
            '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;'
            'margin:9px 0 8px 0;"><tr><td width="46" style="height:2px;line-height:2px;font-size:0;'
            'background-color:#B79554;">&nbsp;</td></tr></table>'
            '<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;'
            'font-size:10px;line-height:16px;color:#5F6775;">'
            '%(phone)s%(email)s'
            '<tr><td valign="top" style="padding:1px 10px 1px 0;font-size:9px;font-weight:600;'
            'letter-spacing:1.2px;color:#B79554;">W</td>'
            '<td style="padding:1px 0;"><a href="%(web)s" target="_blank" style="color:#1C2430;'
            'text-decoration:none;">%(web)s</a></td></tr>'
            '%(address)s'
            '</table>'
            '<div style="margin-top:10px;">'
            '<a href="https://www.linkedin.com/company/sgctechai/" target="_blank" style="text-decoration:none;">'
            '<img src="%(icon_linkedin)s" width="14" height="14" alt="LinkedIn" '
            'style="border:0;margin-right:8px;vertical-align:middle;"></a>'
            '<a href="#" style="text-decoration:none;"><img src="%(icon_facebook)s" '
            'width="14" height="14" alt="Facebook" style="border:0;margin-right:8px;vertical-align:middle;"></a>'
            '<a href="#" style="text-decoration:none;"><img src="%(icon_instagram)s" '
            'width="14" height="14" alt="Instagram" style="border:0;margin-right:8px;vertical-align:middle;"></a>'
            '<a href="#" style="text-decoration:none;"><img src="%(icon_youtube)s" '
            'width="14" height="14" alt="YouTube" style="border:0;margin-right:8px;vertical-align:middle;"></a>'
            '<a href="#" style="text-decoration:none;"><img src="%(icon_twitter)s" '
            'width="13" height="13" alt="X" style="border:0;margin-right:8px;vertical-align:middle;"></a>'
            '</div>'
            '</td></tr></table></td></tr>'
            '<tr><td style="background-color:#0F213D;padding:7px 22px;'
            "font-family:'IBM Plex Serif',Georgia,serif;font-size:11px;line-height:14px;color:#F7F4EE;"
            'font-style:italic;">Finance.System.Technology</td></tr>'
            '<tr><td style="padding:6px 22px 8px 22px;border-top:1px solid #ECE7DF;font-size:7px;'
            'line-height:10px;color:#5F6775;">CONFIDENTIAL — This message and any attachments are intended solely for '
            'the addressee. If received in error, please notify the sender and delete all copies.</td></tr>'
            '</table>'
        ) % {
            'font': "'IBM Plex Serif',Georgia,'Times New Roman',serif",
            'name': esc(name),
            'job': esc(job_title),
            'company': esc(company_name),
            'phone': phone_block,
            'email': email_block,
            'address': address_row,
            'web': esc(website.rstrip('/')),
            'logo': img['logo'],
            'icon_linkedin': img['icon_linkedin'],
            'icon_facebook': img['icon_facebook'],
            'icon_instagram': img['icon_instagram'],
            'icon_youtube': img['icon_youtube'],
            'icon_twitter': img['icon_twitter'],
        }