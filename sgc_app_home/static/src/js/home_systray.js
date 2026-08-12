/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

// The stock navbar "Home Menu" toggle (top-left, oi-apps icon) opens Odoo's
// own native app dropdown, not this module's launcher - there was no way
// back to the SGC App Home from inside an app. This adds a dedicated
// systray icon that jumps straight back to it from anywhere.
export class SgcHomeSystray extends Component {
    static template = "sgc_app_home.HomeSystray";
    static props = {};

    setup() {
        this.action = useService("action");
    }

    goHome() {
        this.action.doAction("sgc_app_home.action_sgc_app_home");
    }
}

registry.category("systray").add(
    "sgc_app_home.HomeSystray",
    { Component: SgcHomeSystray },
    { sequence: 1 }
);
