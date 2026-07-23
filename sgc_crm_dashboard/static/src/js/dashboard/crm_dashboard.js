/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onMounted, onWillUnmount, useRef, useState, useEffect } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

export class CrmDashboard extends Component {
    static template = "sgc_crm_dashboard.Dashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.state = useState({
            kpi: {},
            funnel: [],
            stages: [],
            salesperson: [],
            monthly: [],
            teams: [],
            objection_ranking: [],
            loading: true,
            selectedSalesperson: null,
            salespersonDetail: null,
            detailLoading: false,
            isAdmin: false,
            allUsers: [],
            selectedUserId: null,
            currentUserId: null,
        });
        this.chartRefs = {
            stageChart: useRef("stageChart"),
            monthlyChart: useRef("monthlyChart"),
            funnelChart: useRef("funnelChart"),
        };
        this.charts = {};
        this._chartsReady = false;

        onWillUnmount(() => {
            this.destroyCharts();
        });

        onMounted(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard(userId) {
        this.destroyCharts();
        this.state.loading = true;
        try {
            const params = userId ? [userId] : [];
            const data = await this.orm.call("crm.dashboard", "get_dashboard_data", params);
            this.state.kpi = data.kpi;
            this.state.funnel = data.funnel;
            this.state.stages = data.stages;
            this.state.salesperson = data.salesperson;
            this.state.monthly = data.monthly;
            this.state.teams = data.teams;
            this.state.objection_ranking = data.objection_ranking || [];
            this.state.isAdmin = data.is_admin;
            this.state.allUsers = data.all_users || [];
            this.state.selectedUserId = data.selected_user_id || null;
            this.state.currentUserId = data.current_user_id;
            this.state.selectedSalesperson = null;
            this.state.salespersonDetail = null;
        } catch (e) {
            this.notification.add("Failed to load dashboard data", { type: "danger" });
        } finally {
            this.state.loading = false;
        }

        // Wait for OWL to re-render with data, then render charts
        await new Promise((resolve) => setTimeout(resolve, 50));
        await this._ensureChartJs();
        this.renderCharts();
    }

    async _ensureChartJs() {
        if (typeof Chart === "undefined") {
            await loadJS("/web/static/lib/Chart/Chart.js");
        }
    }

    async onFilterChange(ev) {
        const val = ev.target.value;
        const userId = val ? parseInt(val) : null;
        await this.loadDashboard(userId);
    }

    async selectSalesperson(ev) {
        const userId = parseInt(ev.currentTarget.dataset.userId);
        if (!userId) return;
        this.state.selectedSalesperson = userId;
        this.state.detailLoading = true;
        this.state.salespersonDetail = null;
        try {
            const detail = await this.orm.call("crm.dashboard", "get_salesperson_detail", [userId]);
            this.state.salespersonDetail = detail;
        } catch (e) {
            this.notification.add("Failed to load salesperson detail", { type: "danger" });
        } finally {
            this.state.detailLoading = false;
        }
    }

    closeDetail() {
        this.state.selectedSalesperson = null;
        this.state.salespersonDetail = null;
    }

    destroyCharts() {
        Object.values(this.charts).forEach(c => c?.destroy());
        this.charts = {};
    }

    renderCharts() {
        this.renderStageChart();
        this.renderMonthlyChart();
        this.renderFunnelChart();
    }

    // Brand color palette — Premium Executive (Dark + Gold)
    getBrandColors() {
        return {
            gold: "#C7A23A",
            emerald: "#00B67A",
            amber: "#F4B740",
            coral: "#FF5A5F",
            blue: "#4DA3FF",
            muted: "#708090",
            goldLight: "#D4AF37",
            emeraldLight: "#00CC88",
        };
    }

    renderStageChart() {
        const canvas = this.chartRefs.stageChart?.el;
        if (!canvas || !this.state.stages.length) return;
        if (this.charts.stage) this.charts.stage.destroy();
        const labels = this.state.stages.map(s => s.name);
        const data = this.state.stages.map(s => s.count);
        const brand = this.getBrandColors();
        const colors = [
            brand.gold,
            brand.emerald,
            brand.amber,
            brand.blue,
            brand.emeraldLight,
            brand.coral,
            brand.goldLight,
            brand.muted,
        ];
        this.charts.stage = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{ data, backgroundColor: colors.slice(0, data.length), borderWidth: 0 }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { position: "right", labels: { padding: 12, usePointStyle: true } } },
                cutout: "55%",
            },
        });
    }

    renderMonthlyChart() {
        const canvas = this.chartRefs.monthlyChart?.el;
        if (!canvas || !this.state.monthly.length) return;
        if (this.charts.monthly) this.charts.monthly.destroy();
        const labels = this.state.monthly.map(m => m.month);
        const brand = this.getBrandColors();
        this.charts.monthly = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    { label: "New Leads", data: this.state.monthly.map(m => m.new), backgroundColor: brand.gold, borderRadius: 4 },
                    { label: "Won", data: this.state.monthly.map(m => m.won), backgroundColor: brand.emerald, borderRadius: 4 },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.12)" }, ticks: { color: "#A7B4C6" } },
                    x: { grid: { display: false }, ticks: { color: "#A7B4C6" } },
                },
                plugins: { legend: { labels: { usePointStyle: true, padding: 16 } } },
            },
        });
    }

    renderFunnelChart() {
        const canvas = this.chartRefs.funnelChart?.el;
        if (!canvas || !this.state.funnel.length) return;
        if (this.charts.funnel) this.charts.funnel.destroy();
        const labels = this.state.funnel.map(s => s.name);
        const data = this.state.funnel.map(s => s.count);
        const maxVal = Math.max(...data, 1);
        const brand = this.getBrandColors();
        const colors = data.map((v) => {
            const ratio = v / maxVal;
            if (ratio > 0.5) return brand.gold;
            if (ratio > 0.2) return brand.emerald;
            if (ratio > 0.05) return brand.amber;
            return brand.blue;
        });
        this.charts.funnel = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [{ data, backgroundColor: colors, borderRadius: 4, barThickness: 28 }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.12)" }, ticks: { color: "#A7B4C6", callback: v => v.toLocaleString() } },
                    y: { grid: { display: false }, ticks: { color: "#A7B4C6" } },
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const v = ctx.raw;
                                const pct = data[0] > 0 ? ((v / data[0]) * 100).toFixed(1) : 0;
                                return `${v.toLocaleString()} leads (${pct}% of total)`;
                            },
                        },
                    },
                },
            },
        });
    }

    formatCurrency(val) {
        return new Intl.NumberFormat("en-US", { style: "currency", currency: "AED", maximumFractionDigits: 0 }).format(val || 0);
    }

    formatNumber(val) {
        return new Intl.NumberFormat("en-US").format(val || 0);
    }

    daysColor(days) {
        if (days === null || days === undefined) return "#708090";
        const brand = this.getBrandColors();
        if (days <= 3) return brand.emerald;
        if (days <= 7) return brand.amber;
        if (days <= 14) return brand.gold;
        return brand.coral;
    }

    daysLabel(days) {
        if (days === null || days === undefined) return "No activity";
        return days + "d";
    }

    filterMoveToday() {
        const self = this;
        this.orm.call("crm.dashboard", "get_moved_today_leads", []).then(leadIds => {
            if (!leadIds || leadIds.length === 0) {
                self.notification.add("No leads moved out of New stage today", { type: "info" });
                return;
            }
            self.action.doAction({
                type: "ir.actions.act_window",
                res_model: "crm.lead",
                views: [[false, "list"], [false, "form"]],
                domain: [["id", "in", leadIds]],
                context: {},
                name: "Leads Moved Today",
            });
        }).catch(e => {
            self.notification.add("Failed to fetch moved leads", { type: "danger" });
        });
    }
}

registry.category("actions").add("crm_dashboard", CrmDashboard);
