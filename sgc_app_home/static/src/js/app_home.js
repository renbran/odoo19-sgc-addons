/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

export class SgcAppHome extends Component {
    static template = "sgc_app_home.Home";
    static props = { ...standardActionServiceProps };

    setup() {
        this.menu = useService("menu");
        this.orm = useService("orm");
        this.state = useState({ query: "", meta: {} });

        onWillStart(async () => {
            const apps = this.menu.getApps();
            const menuIds = apps.map((app) => app.id);
            if (menuIds.length) {
                this.state.meta = await this.orm.call("sgc.app.home", "get_app_meta", [menuIds]);
            }
        });
    }

    get apps() {
        const apps = this.menu.getApps();
        const query = this.state.query.trim().toLowerCase();
        const withMeta = apps.map((app) => {
            const meta = this.state.meta[app.id] || {};
            return {
                ...app,
                icon: meta.icon || "/sgc_app_home/static/src/img/apps/default_app.png",
                keywords: meta.keywords || [],
            };
        });
        if (!query) {
            return withMeta;
        }
        return withMeta.filter((app) => {
            if (app.name.toLowerCase().includes(query)) {
                return true;
            }
            return app.keywords.some((keyword) => keyword.includes(query));
        });
    }

    openApp(app) {
        this.menu.selectMenu(app);
    }

    onTileKeydown(app, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openApp(app);
        }
    }
}

registry.category("actions").add("sgc_app_home.home", SgcAppHome);
