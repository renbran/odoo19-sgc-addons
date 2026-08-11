from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sgc_banner_text = fields.Char(
        string="Gamification Banner Text",
        config_parameter="sgc_banne_popup.banner_text",
        help="Shown once per browser session across the backend. Leave blank to disable the banner.",
    )
    sgc_banner_price_pool = fields.Char(
        string="Gamification Prize Pool (AED)",
        config_parameter="sgc_banne_popup.price_pool",
        help="Shown in the banner when greater than 0. Leave at 0 to hide the prize pool figure.",
    )
