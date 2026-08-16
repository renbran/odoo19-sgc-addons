/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Thin RPC wrapper. It holds NO business logic: every number shown by the
 * banner is computed server side by `sgc.ces.kpi.service`. Drill-down actions
 * are also produced server side, so the client never builds a domain.
 */
export const cesKpiService = {
    dependencies: ["orm", "action"],
    start(env, { orm, action }) {
        let inflight = null;

        return {
            /** Summary for the current user. */
            async fetchMySummary() {
                if (inflight) {
                    return inflight;
                }
                inflight = orm
                    .call("sgc.ces.kpi.service", "get_my_ces_kpi_summary", [])
                    .finally(() => {
                        inflight = null;
                    });
                return inflight;
            },

            /** Summary for another user (manager/admin only, enforced server side). */
            async fetchSummaryFor(userId) {
                return orm.call("sgc.ces.kpi.service", "get_ces_kpi_summary", [userId]);
            },

            /** Reviewer detail for one gate instance. */
            async fetchGateReviewSummary(gateInstanceId) {
                return orm.call("sgc.ces.kpi.service", "get_gate_review_summary", [
                    gateInstanceId,
                ]);
            },

            /** Open a server-generated drill-down. `kind` is "requirement" or "kpi". */
            async openDrilldown(kind, refId) {
                const act = await orm.call("sgc.ces.kpi.service", "get_drilldown_action", [
                    kind,
                    refId,
                ]);
                if (act) {
                    await action.doAction(act);
                }
            },
        };
    },
};

registry.category("services").add("sgc_ces_kpi_service", cesKpiService);
