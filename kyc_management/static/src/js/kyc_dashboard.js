/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class KycDashboard extends Component {
    static template = "kyc_management.KycDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            total: 0,
            draft: 0,
            submitted: 0,
            approved: 0,
            rejected: 0,
            pending_review: 0,
            recent: [],
            loading: true,
            error: false,
        });

        onWillStart(async () => {
            await this.fetchData();
        });
    }

    async fetchData() {
        this.state.loading = true;
        this.state.error = false;
        try {
            // Batch all counts in one round-trip using searchCount per state
            const states = ["draft", "submitted", "approved", "rejected", "pending_review"];
            await Promise.all(
                states.map(async (st) => {
                    this.state[st] = await this.orm.searchCount("kyc.application", [["state", "=", st]]);
                })
            );
            this.state.total = await this.orm.searchCount("kyc.application", []);

            // Recent 10 applications
            this.state.recent = await this.orm.searchRead(
                "kyc.application",
                [],
                ["kyc_id", "first_name", "last_name", "email", "state", "submitted_date", "create_date"],
                { order: "create_date desc", limit: 10 }
            );
        } catch (e) {
            console.error("KYC Dashboard: failed to load data", e);
            this.state.error = true;
            this.notification.add(
                _t("KYC Dashboard failed to load. Please refresh."),
                { type: "danger", sticky: false }
            );
        } finally {
            this.state.loading = false;
        }
    }

    openApplications(state) {
        const domain = state ? [["state", "=", state]] : [];
        const label = this.stateLabel(state);
        const name = state
            ? _t("KYC Applications \u2014 %s", label)
            : _t("All KYC Applications");
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: "kyc.application",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openApplication(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("KYC Application"),
            res_model: "kyc.application",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatDate(dt) {
        if (!dt) return "\u2014";
        try {
            return new Date(dt).toLocaleDateString("en-GB", {
                day: "2-digit",
                month: "short",
                year: "numeric",
            });
        } catch {
            return dt;
        }
    }

    stateLabel(state) {
        const map = {
            draft: _t("Draft"),
            submitted: _t("Submitted"),
            approved: _t("Approved"),
            rejected: _t("Rejected"),
            pending_review: _t("Pending Review"),
        };
        return map[state] || state;
    }

    stateBadgeClass(state) {
        const map = {
            draft: "text-bg-secondary",
            submitted: "text-bg-primary",
            approved: "text-bg-success",
            rejected: "text-bg-danger",
            pending_review: "text-bg-warning",
        };
        return map[state] || "text-bg-secondary";
    }
}

KycDashboard.props = ["*"];

registry.category("actions").add("kyc.dashboard", KycDashboard);
