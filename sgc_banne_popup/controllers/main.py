"""SGC Banner/Popup - persistent gamification banner with price pool."""
from odoo import http, fields

env = env  # noqa: F821


class BannePopupController(http.Controller):

    @http.route('/sgc/banne_popup', type='http', auth='user', website=True, csrf=False)
    def banne_popup(self, **kwargs):
        price_pool = http.request.env['ir.config_parameter'].sudo().get_param(
            'sgc_banne_popup.price_pool'
        ) or '0'
        banner_text = http.request.env['ir.config_parameter'].sudo().get_param(
            'sgc_banne_popup.banner_text'
        ) or ''
        return http.request.render('sgc_banne_popup.banner', {
            'price_pool': price_pool,
            'banner_text': banner_text,
        })