/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onPatched, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { EnterpriseFilterBar } from "./enterprise_filter_bar";
import { attachDrilldownHandler } from "./drilldown_handler";

/**
 * Enterprise report client action: EnterpriseFilterBar + report table,
 * replacing the legacy stacked-wizard-form workflow for one report at a
 * time. ``report_type`` comes from the action's context so the same
 * component serves every report — nothing here is Balance-Sheet-specific;
 * Balance Sheet is only the first report wired to this action while the
 * pattern is being proven out.
 *
 * Filter values collected by EnterpriseFilterBar are keyed by *filter key*
 * (e.g. "date", "compare"), not by wizard field name. ``_filterValuesToWizardVals``
 * expands them using each filter's ``wizard_field`` declaration from the
 * metadata registry — this is the one place that bridges "UI filter key"
 * to "wizard field name", so no other code needs to know the mapping.
 */
export class SgcReportClientAction extends Component {
    static template = "sgc_dynamic_financial_report.SgcReportClientAction";
    static components = { EnterpriseFilterBar };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.reportRootRef = useRef("reportRoot");
        this.reportType = this.props.action.context.report_type || "balance_sheet";
        this.state = useState({
            wizardId: null,
            reportHtml: markup(""),
            filterDefs: null,
            generating: false,
            error: null,
        });

        onWillStart(async () => {
            this.state.filterDefs = await rpc("/sgc/dfr/metadata", {});
            const [wizardId] = await this.orm.create("sgc.financial.report.wizard", [
                { report_type: this.reportType },
            ]);
            this.state.wizardId = wizardId;
        });

        // Drill-down: attach a single click delegate on the report
        // container so account rows can be expanded inline to view
        // their journal entries (restores the per-account expand/
        // collapse interaction). attachDrilldownHandler is idempotent
        // (guarded by a dataset flag), so calling on both mount and
        // every patch is safe.
        onMounted(() => this._attachDrilldownIfReady());
        onPatched(() => this._attachDrilldownIfReady());
    }

    _attachDrilldownIfReady() {
        if (!this.state.wizardId) return;
        // `this.el` is not defined on Odoo 19 components; instead the
        // template marks the report-root div with t-ref="reportRoot"
        // and we read it via useRef (initializes to {el: undefined}).
        const root = this.reportRootRef && this.reportRootRef.el;
        if (!root) return;
        const container = root.querySelector(".o_sgc_report_container");
        if (container) {
            attachDrilldownHandler(container, this.state.wizardId);
        }
    }

    /** Expand {filterKey: value} into {wizard_field_name: value}. */
    _filterValuesToWizardVals(values) {
        const filters = (this.state.filterDefs && this.state.filterDefs.filters) || {};
        const vals = {};
        for (const [key, value] of Object.entries(values)) {
            const def = filters[key];
            if (!def || !def.wizard_field || value === undefined) {
                continue;
            }
            if (Array.isArray(def.wizard_field)) {
                // e.g. date range -> (date_from, date_to)
                const [fromField, toField] = def.wizard_field;
                if (Array.isArray(value)) {
                    vals[fromField] = value[0] || false;
                    vals[toField] = value[1] || false;
                }
            } else if (def.widget === "many2many_tags") {
                vals[def.wizard_field] = [[6, 0, Array.isArray(value) ? value : []]];
            } else {
                vals[def.wizard_field] = value;
            }
        }
        return vals;
    }

    async onGenerate(values) {
        this.state.generating = true;
        this.state.error = null;
        try {
            const wizardVals = this._filterValuesToWizardVals(values);
            if (Object.keys(wizardVals).length) {
                await this.orm.write("sgc.financial.report.wizard", [this.state.wizardId], wizardVals);
            }
            const response = await fetch(`/sgc/dfr/preview/${this.state.wizardId}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": session.csrf_token,
                },
                body: JSON.stringify({}),
            });
            const result = await response.json();
            if (result.error) {
                this.state.error = result.error;
            } else {
                this.state.reportHtml = markup(result.html || "");
            }
        } finally {
            this.state.generating = false;
        }
    }

    async onExport(values) {
        const wizardVals = this._filterValuesToWizardVals(values);
        if (Object.keys(wizardVals).length) {
            await this.orm.write("sgc.financial.report.wizard", [this.state.wizardId], wizardVals);
        }
        const exportAction = await this.orm.call(
            "sgc.financial.report.wizard",
            "action_export_xlsx",
            [[this.state.wizardId]]
        );
        this.action.doAction(exportAction);
    }

    /** Secondary/optional export - XLSX (onExport) stays the primary
     * export button; PDF is offered alongside it, never replacing the
     * on-screen preview as the default view. */
    async onExportPdf(values) {
        const wizardVals = this._filterValuesToWizardVals(values);
        if (Object.keys(wizardVals).length) {
            await this.orm.write("sgc.financial.report.wizard", [this.state.wizardId], wizardVals);
        }
        const exportAction = await this.orm.call(
            "sgc.financial.report.wizard",
            "action_print_pdf",
            [[this.state.wizardId]]
        );
        this.action.doAction(exportAction);
    }
}

registry.category("actions").add("sgc_dfr.report_client_action", SgcReportClientAction);
