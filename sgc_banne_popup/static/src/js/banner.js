/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

const SESSION_KEY = "sgc_banne_popup_shown";

export class SgcBannePopup extends Component {
    static template = "sgc_banne_popup.Banner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({ visible: false, bannerText: "", pricePool: 0 });

        onWillStart(async () => {
            if (sessionStorage.getItem(SESSION_KEY)) {
                return;
            }
            let config;
            try {
                config = await this.orm.call("sgc.banne.popup", "get_config", []);
            } catch (e) {
                return;
            }
            if (!config.banner_text && !(config.price_pool > 0)) {
                return;
            }
            this.state.bannerText = config.banner_text;
            this.state.pricePool = config.price_pool;
            this.state.visible = true;
            sessionStorage.setItem(SESSION_KEY, "1");
        });
    }

    dismiss() {
        this.state.visible = false;
    }
}

registry.category("main_components").add("SgcBannePopup", { Component: SgcBannePopup });
