/** @odoo-module **/
import { registry } from "@web/core/registry";

export const sgcOutreachPopupService = {
    dependencies: ["bus_service", "action"],
    start(env, { bus_service, action }) {
        bus_service.subscribe("sgc_outreach_popup", (payload) => {
            if (payload && payload.action) {
                action.doAction(payload.action);
            }
        });
    },
};

registry.category("services").add("sgc_outreach_popup", sgcOutreachPopupService);
