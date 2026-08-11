"""SGC Banner/Popup - standalone preview page for the session banner.

The actual popup shown to users is an OWL main_component
(static/src/js/banner.js), not this route - this only serves as a
directly-linkable preview of the currently configured banner.
"""
from odoo import http
from odoo.http import request


class SgcBannePopupController(http.Controller):

    @http.route('/sgc/banne_popup', type='http', auth='user', website=True, csrf=False)
    def banne_popup(self, **kwargs):
        icp = request.env['ir.config_parameter'].sudo()
        price_pool = icp.get_param('sgc_banne_popup.price_pool') or '0'
        banner_text = icp.get_param('sgc_banne_popup.banner_text') or ''
        return request.render('sgc_banne_popup.banner', {
            'price_pool': price_pool,
            'banner_text': banner_text,
        })
