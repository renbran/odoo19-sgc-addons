/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

/**
 * Team Daily Performance dashboard.
 *
 * Client action for a Team Leader (CES KPI Manager) or Administrator: shows
 * today's KPI progress for every salesperson on a sales team the caller
 * leads (every team for an administrator). Read-only; all numbers come from
 * `sgc.ces.kpi.service.get_team_kpi_overview()`, which enforces access
 * server side exactly like the personal banner.
 */
export class SgcCesTeamKpiDashboard extends Component {
    static template = "sgc_ces_kpi_banner.TeamDashboard";
    static props = ["*"];

    setup() {
        this.kpi = useService("sgc_ces_kpi_service");
        this.state = useState({
            loaded: false,
            error: "",
            teams: [],
        });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.teams = await this.kpi.fetchTeamOverview();
            this.state.error = "";
        } catch (error) {
            this.state.error = (error && error.message) || "unavailable";
            this.state.teams = [];
        } finally {
            this.state.loaded = true;
        }
    }

    barClass(kpi) {
        return kpi.achieved ? "o_sgc_ces_kpi_ok" : "o_sgc_ces_kpi_warn";
    }
}

registry.category("actions").add("sgc_ces_team_kpi_dashboard", SgcCesTeamKpiDashboard);
