/** @odoo-module */
import { registry } from "@web/core/registry";
import { download } from "@web/core/network/download";

registry.category("ir.actions.report handlers").add("xlsx", async (action, options, env) => {
    if (action.report_type !== "xlsx") {
        return false;
    }

    env.services.ui.block();
    try {
        await download({
            url: "/xlsx_report",
            data: action.data,
            error: (error) => {
                throw error;
            },
        });
    } finally {
        env.services.ui.unblock();
    }

    if (action.close_on_report_download) {
        const { onClose } = options;
        return env.services.action.doAction(
            { type: "ir.actions.act_window_close" },
            { onClose }
        );
    }

    if (options.onClose) {
        options.onClose();
    }

    return true;
});
