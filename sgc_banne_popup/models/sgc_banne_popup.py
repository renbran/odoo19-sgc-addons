from odoo import api, models


class SgcBannePopup(models.AbstractModel):
    _name = "sgc.banne.popup"
    _description = "SGC Banner/Popup - read-only config for the session banner"

    @api.model
    def get_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        price_pool_raw = icp.get_param("sgc_banne_popup.price_pool") or "0"
        try:
            price_pool = float(price_pool_raw)
        except ValueError:
            price_pool = 0.0
        return {
            "banner_text": icp.get_param("sgc_banne_popup.banner_text") or "",
            "price_pool": price_pool,
        }
