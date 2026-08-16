/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onWillUnmount, useState, useRef } from "@odoo/owl";

const STORAGE_KEY = "sgc_ces_kpi_banner.collapsed";
const REFRESH_MS = 120000;

/**
 * Floating CES KPI banner.
 *
 * - Registered in `main_components` so it persists across actions.
 * - Renders nothing at all unless the server says the current user is a CES
 *   and the banner is enabled, so it can never disturb other users.
 * - Collapsed/expanded state lives in localStorage only; no server round trip
 *   and no user preference record.
 */
export class SgcCesKpiBanner extends Component {
    static template = "sgc_ces_kpi_banner.Banner";
    static props = {};

    setup() {
        this.kpi = useService("sgc_ces_kpi_service");
        this.panelRef = useRef("panel");
        this.state = useState({
            loaded: false,
            visible: false,
            collapsed: this.readCollapsed(),
            summary: null,
            error: "",
        });

        onWillStart(async () => {
            await this.load();
            this.timer = setInterval(() => this.load(), REFRESH_MS);
        });
        onWillUnmount(() => {
            if (this.timer) {
                clearInterval(this.timer);
            }
        });
    }

    readCollapsed() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) !== "false";
        } catch {
            return true;
        }
    }

    writeCollapsed(value) {
        try {
            window.localStorage.setItem(STORAGE_KEY, value ? "true" : "false");
        } catch {
            // Private browsing or storage disabled: state simply is not persisted.
        }
    }

    async load() {
        try {
            const summary = await this.kpi.fetchMySummary();
            this.state.summary = summary;
            this.state.visible = Boolean(summary && summary.enabled && summary.is_ces);
            this.state.error = "";
        } catch (error) {
            this.state.error = (error && error.message) || "unavailable";
            this.state.visible = false;
        } finally {
            this.state.loaded = true;
        }
    }

    toggle() {
        this.state.collapsed = !this.state.collapsed;
        this.writeCollapsed(this.state.collapsed);
        if (!this.state.collapsed) {
            this.load();
        }
    }

    onKeydown(ev) {
        if (ev.key === "Escape" && !this.state.collapsed) {
            ev.stopPropagation();
            this.toggle();
        }
    }

    get primaryGate() {
        const gates = (this.state.summary && this.state.summary.gates) || [];
        return gates.length ? gates[0] : null;
    }

    get nextAction() {
        return (this.state.summary && this.state.summary.next_action) || null;
    }

    get headlineLabel() {
        const gate = this.primaryGate;
        if (!gate) {
            return this.env._t ? this.env._t("CES KPI") : "CES KPI";
        }
        return `${gate.name} - ${Math.round(gate.score)}%`;
    }

    healthClass(health) {
        if (health === "on_track") {
            return "o_sgc_ces_kpi_ok";
        }
        if (health === "at_risk") {
            return "o_sgc_ces_kpi_warn";
        }
        return "o_sgc_ces_kpi_bad";
    }

    barClass(requirement) {
        if (requirement.achieved) {
            return "o_sgc_ces_kpi_ok";
        }
        return requirement.level === "mandatory"
            ? "o_sgc_ces_kpi_bad"
            : "o_sgc_ces_kpi_warn";
    }

    async openRequirement(requirement) {
        if (!requirement.has_drilldown) {
            return;
        }
        await this.kpi.openDrilldown("requirement", requirement.id);
    }

    async openKpi(kpi) {
        if (!kpi.has_drilldown) {
            return;
        }
        await this.kpi.openDrilldown("kpi", kpi.target_id);
    }

    async openNextAction() {
        const next = this.nextAction;
        if (!next || !next.has_drilldown || next.kind === "none") {
            return;
        }
        await this.kpi.openDrilldown(next.kind, next.ref_id);
    }
}

registry.category("main_components").add("sgc_ces_kpi_banner.Banner", {
    Component: SgcCesKpiBanner,
});
