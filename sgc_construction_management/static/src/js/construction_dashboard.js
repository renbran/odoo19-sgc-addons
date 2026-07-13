/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

/* ============================================================================
   SGC Construction Dashboard - Premium Executive View
   ============================================================================ */

const THEME_KEY = "sgc-dashboard-theme";

class ConstructionDashboard extends Component {
    static template = "ConstructionDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.userName = user.name || "";
        this.userLogin = user.login || "";
        this.userInitials = this.userName
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((part) => part[0].toUpperCase())
            .join("") || "?";
        this.mapRef = useRef("mapViewport");
        this.healthMatrixRef = useRef("healthMatrix");
        this.financialChartRef = useRef("financialChart");

        this.state = useState({
            // KPIs
            total_revenue: 0,
            total_costs: 0,
            net_profit: 0,
            active_work_in_progress: 0,
            critical_risk_count: 0,
            wip_value: 0,
            receivables: 0,
            open_rfqs: 0,
            critical_ncrs: 0,
            equipment_utilization: 0,
            total_contract_value: 0,
            pending_billing: 0,
            overdue_invoices: 0,
            manhours_logged: 0,

            // Status breakdowns
            projects_active: 0,
            projects_completed: 0,
            projects_on_hold: 0,
            projects_delayed: 0,
            emirate_counts: {
                abu_dhabi: 0, dubai: 0, sharjah: 0, ajman: 0,
                umm_al_quwain: 0, ras_al_khaimah: 0, fujairah: 0,
            },

            // Lists
            projects: [],
            alerts: [],
            milestones: [],
            wo_by_state: { draft: 0, confirmed: 0, in_progress: 0, done: 0, cancelled: 0 },
            mrr_by_state: { draft: 0, submitted: 0, approved: 0, received: 0 },

            // Company / currency
            company_name: "Construction",
            currency_symbol: "",
            currency_id: null,

            // Chart period toggle
            financial_period: "ytd",

            // Theme
            theme: "light",
            loading: true,
        });

        onWillStart(async () => {
            // Restore theme preference
            try {
                const stored = window.localStorage.getItem(THEME_KEY);
                if (stored === "dark" || stored === "light") {
                    this.state.theme = stored;
                } else {
                    this.state.theme = window.matchMedia &&
                        window.matchMedia("(prefers-color-scheme: dark)").matches
                        ? "dark"
                        : "light";
                }
            } catch (_) {
                this.state.theme = "light";
            }
            document.documentElement.setAttribute("data-theme", this.state.theme);

            await this.loadData();
        });

        onMounted(() => {
            // Render map immediately (with possibly-empty data) so the viewport
            // is never blank, even before loadData finishes.
            this.renderMap();
            this.renderHealthMatrix();
            this.renderFinancialChart();
        });
    }

    /* ----------------------------- DATA ----------------------------- */
    async loadData() {
        try {
            // Resolve company currency. We use the default company (limit 1)
            // rather than relying on the OWL "user" service which is not
            // always available in client actions. The user's company_id
            // usually matches the default for single-company setups.
            let companyCurrency = null;
            try {
                const comp = await this.orm.searchRead(
                    "res.company",
                    [],
                    ["currency_id", "name"],
                    { limit: 1, order: "id" }
                );
                companyCurrency = comp[0]?.currency_id || null;
                this.state.company_name = comp[0]?.name || this.state.company_name;
            } catch (e) {
                console.warn("Currency lookup failed", e);
            }
            this.state.currency_symbol = companyCurrency?.[1] || "";
            this.state.currency_id = companyCurrency?.[0] || null;

            // Projects (rich payload for KPI + matrix + alerts)
            const projects = await this.orm.searchRead(
                "construction.project",
                [],
                [
                    "name", "state", "contract_value", "currency_id",
                    "latitude", "longitude", "emirate",
                    "progress", "planned_progress", "budget_consumed",
                    "rag_status", "end_date",
                    "total_billed", "total_expenses",
                    "project_manager_id", "margin_percent", "open_ncr_count", "last_site_diary",
                ],
                { order: "name" }
            );

            // Work orders: count by state (searchCount loops - OWL ORM has no readGroup)
            const safe = (p) => p.catch((e) => { console.warn("safe fetch failed", e); return 0; });
            const [woDraft, woConfirmed, woInProgress, rfqCount, ncrCount] = await Promise.all([
                safe(this.orm.searchCount("construction.work.order", [["state", "=", "draft"]])),
                safe(this.orm.searchCount("construction.work.order", [["state", "=", "confirmed"]])),
                safe(this.orm.searchCount("construction.work.order", [["state", "=", "in_progress"]])),
                safe(this.orm.searchCount("construction.material.requisition", [["state", "=", "submitted"]])),
                safe(this.orm.searchCount("construction.quality.check", [["state", "in", ["draft", "in_progress", "failed"]]])),
            ]);
            const activeWOs = woDraft + woConfirmed + woInProgress;

            // Receivables from posted + unpaid customer invoices (sum amount_residual)
            let receivables = 0, overdue_amount = 0;
            try {
                const openInvoices = await this.orm.searchRead(
                    "account.move",
                    [["move_type", "=", "out_invoice"], ["state", "=", "posted"], ["payment_state", "!=", "paid"]],
                    ["amount_residual", "invoice_date_due", "invoice_date"]
                );
                receivables = openInvoices.reduce(
                    (s, m) => s + (m.amount_residual || 0), 0
                );

                // Overdue invoices (due date in past)
                const today = new Date().toISOString().slice(0, 10);
                const overdueInvoices = await this.orm.searchRead(
                    "account.move",
                    [
                        ["move_type", "=", "out_invoice"],
                        ["state", "=", "posted"],
                        ["payment_state", "!=", "paid"],
                        ["invoice_date_due", "<", today],
                    ],
                    ["amount_residual", "invoice_date_due", "partner_id", "name"]
                );
                overdue_amount = overdueInvoices.reduce(
                    (s, m) => s + (m.amount_residual || 0), 0
                );
            } catch (e) {
                console.warn("Receivables fetch failed", e);
            }

            // Pending billing: RA bills in approved state (waiting invoice)
            let pending_billing = 0;
            try {
                // construction.ra.billing has 'total_amount' (not 'amount_total')
                const pendingBillingRes = await this.orm.searchRead(
                    "construction.ra.billing",
                    [["state", "=", "approved"]],
                    ["total_amount"]
                );
                pending_billing = pendingBillingRes.reduce(
                    (s, r) => s + (r.total_amount || 0), 0
                );
            } catch (_) {}

            // Project status counts
            const [projects_active, projects_completed, projects_on_hold] = await Promise.all([
                safe(this.orm.searchCount("construction.project", [["state", "=", "active"]])),
                safe(this.orm.searchCount("construction.project", [["state", "=", "completed"]])),
                safe(this.orm.searchCount("construction.project", [["state", "=", "on_hold"]])),
            ]);
            const projects_delayed = projects.filter(
                (p) => p.rag_status === "red" || p.rag_status === "orange"
            ).length;

            // Work order state breakdown (for status grid)
            const wo_by_state = { draft: 0, confirmed: 0, in_progress: 0, done: 0, cancelled: 0 };
            for (const state of Object.keys(wo_by_state)) {
                wo_by_state[state] = await safe(this.orm.searchCount(
                    "construction.work.order", [["state", "=", state]]
                ));
            }

            // Material requisition state breakdown
            const mrr_by_state = { draft: 0, submitted: 0, approved: 0, received: 0 };
            for (const state of Object.keys(mrr_by_state)) {
                mrr_by_state[state] = await safe(this.orm.searchCount(
                    "construction.material.requisition", [["state", "=", state]]
                ));
            }

            // Upcoming milestones (top 4 work orders by planned_cost or end_date)
            let milestones = [];
            try {
                // construction.work.order has no 'progress' field — use priority instead
                const allWOs = await this.orm.searchRead(
                    "construction.work.order",
                    [["state", "in", ["draft", "confirmed", "in_progress"]]],
                    ["name", "project_id", "state", "planned_cost", "actual_end", "priority"],
                    { order: "actual_end asc", limit: 4 }
                );
                milestones = allWOs.map((w) => ({
                    name: w.name,
                    project: w.project_id ? w.project_id[1] : "",
                    state: w.state,
                    planned_cost: w.planned_cost || 0,
                    due: w.actual_end || "TBD",
                    priority: w.priority || "0",
                }));
            } catch (_) {}

            const total_contract_value = projects.reduce(
                (s, p) => s + (p.contract_value || 0), 0
            );

            // Synthetic manhours estimate (real field may exist later)
            const manhours_logged = projects.reduce(
                (s, p) => s + Math.round(((p.contract_value || 0) / 85000000) * 12500), 0
            );

            // Aggregated KPIs
            const total_revenue = projects.reduce(
                (s, p) => s + (p.total_billed || 0), 0
            );
            const total_costs = projects.reduce(
                (s, p) => s + (p.total_expenses || 0), 0
            );
            const net_profit = total_revenue - total_costs;
            const wip_value = projects
                .filter((p) => p.state === "active")
                .reduce((s, p) => s + ((p.contract_value || 0) - (p.total_billed || 0)), 0);

            // RAG / risk rollup
            const alerts = projects
                .filter((p) => ["red", "orange"].includes(p.rag_status))
                .map((p) => ({
                    project_id: p.id,
                    project_name: p.name,
                    type: p.rag_status === "red" ? "Critical" : "Warning",
                    reason:
                        (p.progress || 0) < (p.planned_progress || 0)
                            ? "Schedule Delay"
                            : "Budget Overrun",
                    detail:
                        (p.progress || 0) < (p.planned_progress || 0)
                            ? `Actual ${(p.progress || 0).toFixed(0)}% vs planned ${(p.planned_progress || 0).toFixed(0)}%`
                            : `Budget consumed ${(p.budget_consumed || 0).toFixed(0)}% of contract value`,
                    delay_impact:
                        p.planned_progress && p.progress
                            ? `${Math.max(0, Math.round(p.planned_progress - p.progress))} days`
                            : "Pending",
                    due_date: p.end_date || "TBD",
                }));

            const critical_risk_count = projects.filter(
                (p) => p.rag_status === "red"
            ).length;

            // Per-emirate project counts (for map overlay) — all 7 emirates,
            // derived client-side from the already-loaded `emirate` field.
            const emirate_counts = {
                abu_dhabi: 0, dubai: 0, sharjah: 0, ajman: 0,
                umm_al_quwain: 0, ras_al_khaimah: 0, fujairah: 0,
            };
            for (const p of projects) {
                if (p.emirate && p.emirate in emirate_counts) {
                    emirate_counts[p.emirate]++;
                }
            }

            // Demo equipment utilization (replace with real data hook later)
            const equipment_utilization = 82;

            this.state.projects = projects;
            this.state.total_revenue = total_revenue;
            this.state.total_costs = total_costs;
            this.state.net_profit = net_profit;
            this.state.active_work_in_progress = activeWOs;
            this.state.critical_risk_count = critical_risk_count;
            this.state.wip_value = wip_value;
            this.state.receivables = receivables;
            this.state.open_rfqs = rfqCount;
            this.state.critical_ncrs = ncrCount;
            this.state.equipment_utilization = equipment_utilization;
            this.state.total_contract_value = total_contract_value;
            this.state.pending_billing = pending_billing;
            this.state.overdue_invoices = overdue_amount;
            this.state.manhours_logged = manhours_logged;
            this.state.projects_active = projects_active;
            this.state.projects_completed = projects_completed;
            this.state.projects_on_hold = projects_on_hold;
            this.state.projects_delayed = projects_delayed;
            this.state.emirate_counts = emirate_counts;
            this.state.wo_by_state = wo_by_state;
            this.state.mrr_by_state = mrr_by_state;
            this.state.milestones = milestones;
            this.state.alerts = alerts;
            this.state.loading = false;

            // Map needs DOM + data
            this.renderMap();

            // Re-render charts with real data
            this.renderHealthMatrix();
            this.renderFinancialChart();
        } catch (e) {
            console.error("Construction dashboard loadData error:", e);
            this.state.loading = false;
        }
    }

    /* ----------------------------- MAP ----------------------------- */
    renderMap() {
        const el = this.mapRef.el;
        if (!el) return;
        if (!window.L) {
            // Leaflet not yet loaded; try again shortly
            setTimeout(() => this.renderMap(), 150);
            return;
        }

        // Tear down previous instance to avoid duplicate overlays
        if (this._leafletMap) {
            this._leafletMap.remove();
            this._leafletMap = null;
        }

        const dark = this.state.theme === "dark";

        // Build project pins (real or demo)
        const groups = {};
        for (const p of this.state.projects) {
            if (!p.latitude || !p.longitude) continue;
            const key = `${p.latitude.toFixed(2)}_${p.longitude.toFixed(2)}`;
            if (!groups[key]) groups[key] = { lat: p.latitude, lon: p.longitude, projects: [] };
            groups[key].projects.push(p);
        }
        const realPins = Object.values(groups).map((g) => ({
            lat: g.lat, lon: g.lon,
            city: this._cityLabel(g.projects[0]),
            names: g.projects.map((p) => p.name),
            projects: g.projects,
            status: this._worstRag(g.projects),
            contract: g.projects.reduce((s, p) => s + (p.contract_value || 0), 0),
        }));

        const demoPins = [
            { lat: 25.79, lon: 55.94, city: "RAS AL KHAIMAH", names: ["RAK Mixed-Use"], status: "amber", contract: 32000000 },
            { lat: 25.52, lon: 55.77, city: "UMM AL QUWAIN", names: ["UAQ Logistics Hub"], status: "amber", contract: 18000000 },
            { lat: 25.40, lon: 55.51, city: "AJMAN", names: ["Ajman Tower"], status: "green", contract: 24000000 },
            { lat: 25.34, lon: 55.40, city: "SHARJAH", names: ["Marina Development Project"], status: "green", contract: 45000000 },
            { lat: 25.20, lon: 55.27, city: "DUBAI", names: ["Highway Bridge Expansion - Sector 7"], status: "green", contract: 38000000 },
            { lat: 25.13, lon: 56.34, city: "FUJAIRAH", names: ["Fujairah Coastal"], status: "red", contract: 28000000 },
            { lat: 24.45, lon: 54.38, city: "ABU DHABI", names: ["Al Nasr Tower - Residential Complex"], status: "green", contract: 85000000 },
            { lat: 24.20, lon: 55.74, city: "AL AIN", names: ["Al Ain Mall"], status: "green", contract: 32000000 },
            { lat: 25.10, lon: 55.90, city: "DUBAI OUTSKIRTS", names: ["Desert Resort"], status: "amber", contract: 22000000 },
            { lat: 24.80, lon: 55.65, city: "ABU DHABI OUTSKIRTS", names: ["Highway Extension"], status: "red", contract: 41000000 },
            { lat: 25.60, lon: 56.10, city: "EAST COAST", names: ["Coastal Villa"], status: "green", contract: 18000000 },
            { lat: 24.10, lon: 55.30, city: "WESTERN REGION", names: ["Desert Solar Farm"], status: "amber", contract: 56000000 },
            { lat: 25.45, lon: 55.50, city: "AJMAN OUTSKIRTS", names: ["Industrial Zone"], status: "green", contract: 29000000 },
            { lat: 24.65, lon: 54.80, city: "ABU DHABI METRO", names: ["Metro Phase 2"], status: "red", contract: 78000000 },
            { lat: 25.25, lon: 55.40, city: "SHARJAH OUTSKIRTS", names: ["Warehouse Complex"], status: "green", contract: 15000000 },
        ];

        const pins = realPins.length > 0 ? realPins : demoPins;

        // Initialize the Leaflet map centered on UAE
        const map = window.L.map(el, {
            zoomControl: false,
            attributionControl: true,
            scrollWheelZoom: true,
            minZoom: 6,
            maxZoom: 18,
            zoomSnap: 0.5,
        }).setView([24.5, 54.5], 7);

        // Tile layer: CartoDB Dark Matter for dark, Voyager for light
        // Plus a satellite option stored on the map instance for the layer switcher
        const darkTiles = window.L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
        );
        const lightTiles = window.L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
            {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: "abcd",
                maxZoom: 19,
            }
        );
        const satelliteTiles = window.L.tileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            {
                attribution: "Tiles &copy; Esri",
                maxZoom: 19,
            }
        );

        const tiles = dark ? darkTiles : lightTiles;
        tiles.addTo(map);

        // Layer control (top-right of map)
        const baseMaps = {
            "Streets": lightTiles,
            "Dark": darkTiles,
            "Satellite": satelliteTiles,
        };
        window.L.control.layers(baseMaps, null, {
            position: "topright",
            collapsed: true,
        }).addTo(map);

        // Add UAE country outline overlay (high-quality GeoJSON-like path)
        const uaeOutline = this._buildUaeOutline();
        if (uaeOutline) {
            const uaeLayer = window.L.geoJSON(uaeOutline, {
                style: () => ({
                    color: dark ? "#c8a85a" : "#1e40af",
                    weight: 2.2,
                    opacity: 0.85,
                    fillColor: dark ? "#0e1f3e" : "#dbe7f5",
                    fillOpacity: dark ? 0.55 : 0.45,
                    dashArray: "0",
                }),
            }).addTo(map);
            uaeLayer.bringToBack();
        }

        // Zoom controls (custom position to match reference)
        const zoomControl = window.L.control.zoom({ position: "topright" });
        zoomControl.addTo(map);

        // Locate (find me) control - uses browser geolocation
        const LocateControl = window.L.Control.extend({
            onAdd: function () {
                const btn = window.L.DomUtil.create("button", "sgc-locate-btn leaflet-bar leaflet-control");
                btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/><circle cx="12" cy="12" r="8"/></svg>';
                btn.title = "Show my location";
                btn.setAttribute("aria-label", "Show my location");
                btn.onclick = () => {
                    if (!navigator.geolocation) {
                        btn.title = "Geolocation not available";
                        return;
                    }
                    btn.classList.add("sgc-locate-btn--loading");
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            btn.classList.remove("sgc-locate-btn--loading");
                            const { latitude, longitude } = pos.coords;
                            window.L.circleMarker([latitude, longitude], {
                                radius: 8,
                                color: "#3b82f6",
                                fillColor: "#3b82f6",
                                fillOpacity: 0.6,
                                weight: 2,
                            }).addTo(map);
                            map.setView([latitude, longitude], 11, { animate: true });
                        },
                        () => {
                            btn.classList.remove("sgc-locate-btn--loading");
                            btn.title = "Location permission denied";
                        },
                        { enableHighAccuracy: false, timeout: 6000, maximumAge: 60000 }
                    );
                };
                return btn;
            },
        });
        new LocateControl({ position: "topright" }).addTo(map);

        // Add project pin markers using divIcons (no image files needed)
        for (const pin of pins) {
            const color = this._pinColor(pin.status);
            const pulseColor = color;
            const icon = window.L.divIcon({
                className: "sgc-leaflet-pin",
                html: `
                    <div class="sgc-pin-wrap">
                        <div class="sgc-pin-pulse" style="background:${pulseColor};"></div>
                        <div class="sgc-pin-halo" style="background:${pulseColor};"></div>
                        <div class="sgc-pin-core" style="background:${color};"></div>
                    </div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            });
            const marker = window.L.marker([pin.lat, pin.lon], { icon }).addTo(map);
            marker.bindPopup(this._buildPopupHtml(pin, color), {
                className: "sgc-popup-wrapper",
                closeButton: false,
            });
            // Event delegation (not inline onclick=) so we don't have to
            // hand-escape project IDs into HTML attribute/JS-string context.
            marker.on("popupopen", (e) => {
                const node = e.popup.getElement();
                if (!node) return;
                node.querySelectorAll("[data-open-project]").forEach((el) => {
                    el.addEventListener("click", () => {
                        const projectId = parseInt(el.getAttribute("data-open-project"), 10);
                        if (projectId) this._openProjectForm(projectId);
                    });
                });
            });
        }

        this._leafletMap = map;

        // The map now lives in a full-bleed row whose final width/height can
        // settle after Leaflet's own init-time size read (CSS reflow from
        // rows above, fonts loading, etc.). Re-measure once layout has
        // actually painted so tiles don't end up misaligned or gray.
        requestAnimationFrame(() => {
            if (this._leafletMap) {
                this._leafletMap.invalidateSize();
            }
        });
    }

    _pinColor(status) {
        if (status === "red") return "#ef4444";
        if (status === "amber" || status === "orange") return "#f59e0b";
        return "#22c55e";
    }

    _openProjectForm(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "construction.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /* Single-project pin: full detail popup. Multi-project pin (coordinate
       cluster): summary header + a clickable row per project. Demo/fallback
       pins (no backing project record) get the plain summary, no click. */
    _buildPopupHtml(pin, color) {
        const projects = pin.projects || [];
        if (projects.length === 1) {
            const p = projects[0];
            const manager = p.project_manager_id ? this._escapeXml(p.project_manager_id[1]) : "—";
            const margin = typeof p.margin_percent === "number" ? `${p.margin_percent.toFixed(1)}%` : "—";
            const ncrCount = p.open_ncr_count != null ? p.open_ncr_count : "—";
            const completion = p.end_date || "TBD";
            const lastDiary = p.last_site_diary || "No entries logged";
            return `
                <div class="sgc-popup sgc-popup--detail">
                    <div class="sgc-popup__city">${this._escapeXml(p.name)}</div>
                    <div class="sgc-popup__status" style="color:${color};">${this._escapeXml(pin.status.toUpperCase())}</div>
                    <dl class="sgc-popup__fields">
                        <div><dt>Manager</dt><dd>${manager}</dd></div>
                        <div><dt>Progress</dt><dd>${(p.progress || 0).toFixed(0)}%</dd></div>
                        <div><dt>Budget Consumed</dt><dd>${(p.budget_consumed || 0).toFixed(0)}%</dd></div>
                        <div><dt>Contract Value</dt><dd>${this.formatCompact(p.contract_value || 0)}</dd></div>
                        <div><dt>Margin</dt><dd>${margin}</dd></div>
                        <div><dt>Open NCRs</dt><dd>${ncrCount}</dd></div>
                        <div><dt>Expected Completion</dt><dd>${this._escapeXml(String(completion))}</dd></div>
                        <div><dt>Last Site Diary</dt><dd>${this._escapeXml(String(lastDiary))}</dd></div>
                    </dl>
                    <button class="sgc-popup__open-btn" data-open-project="${p.id}">View Project</button>
                </div>
            `;
        }
        const projectList = projects.length
            ? projects.map((p) => `<li data-open-project="${p.id}">${this._escapeXml(p.name)}</li>`).join("")
            : pin.names.map((n) => `<li>${this._escapeXml(n)}</li>`).join("");
        return `
            <div class="sgc-popup">
                <div class="sgc-popup__city">${this._escapeXml(pin.city)}</div>
                <div class="sgc-popup__count">${pin.names.length} project${pin.names.length !== 1 ? "s" : ""} · ${this.formatCompact(pin.contract)}</div>
                <div class="sgc-popup__status" style="color:${color};">${this._escapeXml(pin.status.toUpperCase())}</div>
                <ul class="sgc-popup__list sgc-popup__list--clickable">${projectList}</ul>
            </div>
        `;
    }

    /* Build a GeoJSON-like UAE outline for Leaflet.
       Returns { type: "Feature", geometry: { type: "Polygon", coordinates: [[[lon, lat], ...]] } } */
    _buildUaeOutline() {
        const lonLat = [
            // === Western tail near Sila / Qatar border ===
            [51.50, 24.18], [51.55, 24.25], [51.60, 24.10], [51.70, 24.05],
            [51.85, 24.10], [52.05, 24.20], [52.25, 24.30], [52.40, 24.40],
            [52.55, 24.45], [52.70, 24.50], [52.85, 24.50], [53.00, 24.45],
            // === Abu Dhabi coast ===
            [53.20, 24.50], [53.40, 24.55], [53.55, 24.55], [53.70, 24.55],
            [53.85, 24.55], [54.00, 24.55], [54.15, 24.55], [54.30, 24.50],
            [54.45, 24.45], [54.55, 24.40], [54.65, 24.30], [54.75, 24.15],
            // === Abu Dhabi offshore islands ===
            [54.50, 24.20], [54.40, 24.20], [54.30, 24.15], [54.25, 24.10],
            [54.30, 24.05], [54.40, 24.05], [54.50, 24.10], [54.55, 24.15],
            // === Continue Abu Dhabi coast (Al Ain area) ===
            [54.85, 24.00], [55.00, 23.90], [55.15, 23.80], [55.30, 23.70],
            [55.45, 23.60], [55.55, 23.50], [55.65, 23.45], [55.75, 23.40],
            [55.85, 23.35], [55.95, 23.30], [56.00, 23.25],
            // === Al Ain / inland southeast ===
            [56.05, 23.20], [56.05, 23.30], [56.10, 23.50], [56.15, 23.70],
            [56.20, 23.85], [56.25, 24.00], [56.30, 24.15], [56.35, 24.30],
            // === Fujairah coast (Gulf of Oman) ===
            [56.30, 24.50], [56.25, 24.70], [56.20, 24.90], [56.18, 25.05],
            [56.15, 25.20], [56.18, 25.40], [56.20, 25.55], [56.25, 25.70],
            [56.30, 25.85], [56.35, 26.00],
            // === Musandam exclave (north) ===
            [56.20, 26.30], [56.25, 26.40], [56.20, 26.45], [56.10, 26.45],
            [56.00, 26.40], [55.95, 26.30], [56.00, 26.25], [56.10, 26.25],
            // === Mainland north coast (Ras Al Khaimah area) ===
            [56.00, 26.10], [55.95, 25.95], [55.90, 25.85], [55.85, 25.75],
            [55.80, 25.65], [55.75, 25.55], [55.70, 25.45],
            // === Northern coast (Sharjah, Ajman, UAQ) ===
            [55.65, 25.40], [55.60, 25.35], [55.55, 25.35], [55.50, 25.40],
            [55.45, 25.45], [55.40, 25.45], [55.35, 25.45], [55.30, 25.45],
            [55.25, 25.40], [55.20, 25.35], [55.15, 25.30], [55.10, 25.20],
            // === Dubai coast ===
            [55.05, 25.10], [55.00, 25.05], [54.95, 24.95], [54.90, 24.85],
            [54.85, 24.75], [54.80, 24.70], [54.75, 24.65], [54.70, 24.60],
            // === Abu Dhabi city coast (Persian Gulf) ===
            [54.60, 24.55], [54.50, 24.50], [54.40, 24.45], [54.30, 24.40],
            [54.20, 24.35], [54.10, 24.30], [54.00, 24.25], [53.85, 24.25],
            [53.70, 24.20], [53.55, 24.20], [53.40, 24.20], [53.25, 24.20],
            // === Back to Sila ===
            [53.10, 24.18], [52.95, 24.18], [52.80, 24.20], [52.65, 24.20],
            [52.50, 24.20], [52.35, 24.20], [52.20, 24.20], [52.00, 24.18],
            [51.80, 24.18], [51.65, 24.18], [51.50, 24.18],
        ];
        return {
            type: "Feature",
            geometry: { type: "Polygon", coordinates: [lonLat] },
            properties: { name: "United Arab Emirates" },
        };
    }

    _cityLabel(p) {
        const map = {
            dubai: "Dubai",
            abu_dhabi: "Abu Dhabi",
            sharjah: "Sharjah",
            ajman: "Ajman",
            umm_al_quwain: "Umm Al Quwain",
            ras_al_khaimah: "Ras Al Khaimah",
            fujairah: "Fujairah",
        };
        return map[p.emirate] || "UAE Site";
    }

    /* HD UAE Projects Map - matches the reference design:
       - detailed UAE coastline with all 7 emirates + Persian Gulf label
       - premium glass-morphism callouts with city-colored icons
       - dark navy + gold border color scheme
       - neighboring countries (Saudi Arabia, Oman, Qatar) as cream/sand
       - compass rose, scale bar, status legend
    */
    _buildUaeSvg(pins, dark) {
        const W = 1500, H = 760;
        const minLon = 50.6, maxLon = 57.2, minLat = 22.2, maxLat = 26.8;
        const proj = (lon, lat) => ({
            x: ((lon - minLon) / (maxLon - minLon)) * W,
            y: H - ((lat - minLat) / (maxLat - minLat)) * H,
        });

        /* HIGH-DETAIL UAE outline - 80+ coastline points tracing the
           actual UAE shape: western tail (Sila), Abu Dhabi coast, Dubai
           coast, northern emirates, Musandam exclave, eastern mountains. */
        const uaeMainland = [
            // === Western "tail" near Sila / Qatar border ===
            [51.50, 24.18], [51.55, 24.25], [51.60, 24.10], [51.70, 24.05],
            [51.85, 24.10], [52.05, 24.20], [52.25, 24.30], [52.40, 24.40],
            [52.55, 24.45], [52.70, 24.50], [52.85, 24.50], [53.00, 24.45],
            // === Abu Dhabi coast (south/southwest) ===
            [53.20, 24.50], [53.40, 24.55], [53.55, 24.55], [53.70, 24.55],
            [53.85, 24.55], [54.00, 24.55], [54.15, 24.55], [54.30, 24.50],
            [54.45, 24.45], [54.55, 24.40], [54.65, 24.30], [54.75, 24.15],
            // === Abu Dhabi offshore islands ===
            [54.50, 24.20], [54.40, 24.20], [54.30, 24.15], [54.25, 24.10],
            [54.30, 24.05], [54.40, 24.05], [54.50, 24.10], [54.55, 24.15],
            // === Continue Abu Dhabi coast (south/east toward Al Ain) ===
            [54.85, 24.00], [55.00, 23.90], [55.15, 23.80], [55.30, 23.70],
            [55.45, 23.60], [55.55, 23.50], [55.65, 23.45], [55.75, 23.40],
            [55.85, 23.35], [55.95, 23.30], [56.00, 23.25],
            // === Al Ain / inland southeast ===
            [56.05, 23.20], [56.05, 23.30], [56.10, 23.50], [56.15, 23.70],
            [56.20, 23.85], [56.25, 24.00], [56.30, 24.15], [56.35, 24.30],
            // === Fujairah coast (Gulf of Oman) ===
            [56.30, 24.50], [56.25, 24.70], [56.20, 24.90], [56.18, 25.05],
            [56.15, 25.20], [56.18, 25.40], [56.20, 25.55], [56.25, 25.70],
            [56.30, 25.85], [56.35, 26.00],
            // === Musandam exclave (north) ===
            [56.20, 26.30], [56.25, 26.40], [56.20, 26.45], [56.10, 26.45],
            [56.00, 26.40], [55.95, 26.30], [56.00, 26.25], [56.10, 26.25],
            // === Mainland north coast (Ras Al Khaimah area) ===
            [56.00, 26.10], [55.95, 25.95], [55.90, 25.85], [55.85, 25.75],
            [55.80, 25.65], [55.75, 25.55], [55.70, 25.45],
            // === Northern coast (Sharjah, Ajman, UAQ) ===
            [55.65, 25.40], [55.60, 25.35], [55.55, 25.35], [55.50, 25.40],
            [55.45, 25.45], [55.40, 25.45], [55.35, 25.45], [55.30, 25.45],
            [55.25, 25.40], [55.20, 25.35], [55.15, 25.30], [55.10, 25.20],
            // === Dubai coast ===
            [55.05, 25.10], [55.00, 25.05], [54.95, 24.95], [54.90, 24.85],
            [54.85, 24.75], [54.80, 24.70], [54.75, 24.65], [54.70, 24.60],
            // === Abu Dhabi city coast (Persian Gulf) ===
            [54.60, 24.55], [54.50, 24.50], [54.40, 24.45], [54.30, 24.40],
            [54.20, 24.35], [54.10, 24.30], [54.00, 24.25], [53.85, 24.25],
            [53.70, 24.20], [53.55, 24.20], [53.40, 24.20], [53.25, 24.20],
            // === Back to Sila (close the polygon) ===
            [53.10, 24.18], [52.95, 24.18], [52.80, 24.20], [52.65, 24.20],
            [52.50, 24.20], [52.35, 24.20], [52.20, 24.20], [52.00, 24.18],
            [51.80, 24.18], [51.65, 24.18], [51.50, 24.18],
        ];

        /* Major islands (simplified as separate paths) */
        const islands = [
            // Abu Dhabi offshore islands (Khor Al Bazeel etc.)
            [[54.05, 24.18], [54.15, 24.18], [54.20, 24.22], [54.15, 24.25], [54.05, 24.22]],
            // Das Island area
            [[53.85, 25.10], [53.95, 25.10], [53.95, 25.15], [53.85, 25.15]],
            // Small islands near Sharjah
            [[55.40, 25.30], [55.45, 25.30], [55.45, 25.33], [55.40, 25.33]],
        ];

        /* Neighboring countries (just enough to give context, no precise
           shapes needed - they're decorative) */
        const saudiCoast = [
            [50.8, 22.2], [50.8, 27.0], [51.5, 27.0], [51.6, 26.8],
            [51.6, 25.5], [51.5, 24.2], [51.5, 23.5], [51.7, 23.0],
            [51.5, 22.5], [51.2, 22.3], [50.8, 22.2],
        ];
        const omanCoast = [
            [56.4, 22.2], [57.2, 22.5], [57.2, 27.0], [56.5, 27.0],
            [56.4, 26.5], [56.3, 25.7], [56.4, 25.0], [56.5, 24.5],
            [56.5, 24.0], [56.5, 23.5], [56.4, 23.0], [56.4, 22.5],
        ];
        const qatarStub = [
            [50.6, 24.5], [50.7, 25.3], [51.0, 25.5], [51.5, 25.5],
            [51.5, 24.5], [50.6, 24.5],
        ];
        const iranStub = [
            [56.0, 26.0], [57.2, 26.0], [57.2, 27.0], [56.0, 27.0],
        ];

        const c = dark ? {
            ocean1: "#5b7a9a", ocean2: "#7d9bbb", ocean3: "#a8c0d4",
            land1: "#0e1f3e", land2: "#0a1730", landStroke: "#c8a85a",
            neighborFill: "#e8dec3", neighborStroke: "#c8b88f",
            neighborText: "#8a7a5a",
            cityText: "#ffffff", citySub: "#c8a85a",
            grid: "rgba(255,255,255,0.06)",
            accent: "#d4a857", accentSoft: "rgba(212,168,87,0.4)",
            calloutBg: "#0c1729", calloutBorder: "#c8a85a",
            calloutShadow: "rgba(0,0,0,0.5)",
            text: "#94a3b8", textStrong: "#ffffff",
            statBar: "#c8a85a",
            statusGreen: "#22c55e", statusAmber: "#f59e0b", statusRed: "#ef4444",
            persianGulf: "#3a5572",
        } : {
            ocean1: "#cfe0ee", ocean2: "#b6cee0", ocean3: "#9fbcd4",
            land1: "#0e1f3e", land2: "#0a1730", landStroke: "#c8a85a",
            neighborFill: "#e8dec3", neighborStroke: "#c8b88f",
            neighborText: "#8a7a5a",
            cityText: "#ffffff", citySub: "#c8a85a",
            grid: "rgba(255,255,255,0.06)",
            accent: "#d4a857", accentSoft: "rgba(212,168,87,0.4)",
            calloutBg: "#0c1729", calloutBorder: "#c8a85a",
            calloutShadow: "rgba(0,0,0,0.5)",
            text: "#94a3b8", textStrong: "#ffffff",
            statBar: "#c8a85a",
            statusGreen: "#22c55e", statusAmber: "#f59e0b", statusRed: "#ef4444",
            persianGulf: "#3a5572",
        };

        const pathFromCoords = (coords) =>
            coords.map(([lon, lat], i) => {
                const { x, y } = proj(lon, lat);
                return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
            }).join(" ");

        const uaePath = pathFromCoords(uaeMainland);
        const islandPaths = islands.map(pathFromCoords).join("");

        /* Graticule */
        const grid = [];
        for (let lon = 51; lon <= 57; lon += 1) {
            const x = ((lon - minLon) / (maxLon - minLon)) * W;
            grid.push(`<line x1="${x}" y1="0" x2="${x}" y2="${H}" stroke="${c.grid}" stroke-width="0.5" stroke-dasharray="2 6"/>`);
        }
        for (let lat = 23; lat <= 27; lat += 1) {
            const y = H - ((lat - minLat) / (maxLat - minLat)) * H;
            grid.push(`<line x1="0" y1="${y}" x2="${W}" y2="${y}" stroke="${c.grid}" stroke-width="0.5" stroke-dasharray="2 6"/>`);
        }

        /* Lat/lon axis labels */
        const axisLabels = [];
        for (let lon = 52; lon <= 57; lon += 1) {
            const x = ((lon - minLon) / (maxLon - minLon)) * W;
            axisLabels.push(`<text x="${x}" y="${H - 8}" text-anchor="middle" font-size="10" fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif" opacity="0.6" font-weight="600">${lon}°E</text>`);
        }

        /* 7 emirates with their primary cities */
        const cities = [
            { name: "RAS AL KHAIMAH", lon: 55.95, lat: 25.85, primary: true, align: "end" },
            { name: "UMM AL QUWAIN", lon: 55.80, lat: 25.55, primary: true, align: "end" },
            { name: "AJMAN", lon: 55.55, lat: 25.40, primary: true, align: "end" },
            { name: "SHARJAH", lon: 55.42, lat: 25.30, primary: true, align: "end" },
            { name: "DUBAI", lon: 55.27, lat: 25.05, primary: true, align: "end" },
            { name: "ABU DHABI", lon: 54.45, lat: 24.20, primary: true, align: "middle" },
            { name: "FUJAIRAH", lon: 56.32, lat: 25.18, primary: true, align: "start" },
        ];

        const cityLabels = cities.map((ct) => {
            const { x, y } = proj(ct.lon, ct.lat);
            const fs = 16;
            const fw = 700;
            const letterSpacing = 2.5;
            // Connector from label to a small marker dot
            const anchorX = x;
            const anchorY = y;
            let labelX, textAnchor;
            if (ct.align === "end") {
                labelX = anchorX - 14;
                textAnchor = "end";
            } else if (ct.align === "start") {
                labelX = anchorX + 14;
                textAnchor = "start";
            } else {
                labelX = anchorX;
                textAnchor = "middle";
            }
            // Tiny anchor dot
            return `
                <g>
                    <circle cx="${anchorX}" cy="${anchorY}" r="3" fill="${c.accent}" opacity="0.85"/>
                    <circle cx="${anchorX}" cy="${anchorY}" r="6" fill="${c.accent}" opacity="0.18"/>
                    <text x="${labelX}" y="${anchorY + 5}"
                          font-size="${fs}"
                          font-weight="${fw}"
                          font-family="'Plus Jakarta Sans', sans-serif"
                          fill="${c.cityText}"
                          text-anchor="${textAnchor}"
                          letter-spacing="${letterSpacing}">${ct.name}</text>
                </g>`;
        }).join("\n");

        /* PERSIAN GULF label */
        const gulfCenter = proj(53.0, 26.2);
        const persianGulfLabel = `
            <text x="${gulfCenter.x}" y="${gulfCenter.y}" text-anchor="middle"
                  font-size="16" font-weight="700" letter-spacing="6"
                  font-family="'Plus Jakarta Sans', sans-serif"
                  fill="${c.persianGulf}" opacity="0.7">PERSIAN GULF</text>`;

        /* Project pins + glass-morphism callouts */
        const statusColor = (status) => {
            if (status === "red") return c.statusRed;
            if (status === "amber" || status === "orange") return c.statusAmber;
            return c.statusGreen;
        };

        // Identify which pins should have visible callouts (matching the reference)
        const pinSvg = pins.map((pin, idx) => {
            const { x, y } = proj(pin.lon, pin.lat);
            const color = statusColor(pin.status);
            const delay = idx * 0.4;

            // Decide callout placement (only for selected pins, alt sides)
            const showCallout = pin.showCallout;
            const boxW = 220;
            const boxH = 64;

            let calloutX, calloutY, anchorX;
            if (showCallout) {
                // Place callout so the city name appears prominently
                if (pin.city === "SHARJAH") {
                    calloutX = x - 220 - 60;
                    calloutY = y - 130;
                    anchorX = calloutX + boxW;
                } else if (pin.city === "DUBAI") {
                    calloutX = x - 220 - 80;
                    calloutY = y + 60;
                    anchorX = calloutX + boxW;
                } else if (pin.city === "ABU DHABI") {
                    calloutX = x - 220 - 60;
                    calloutY = y + 80;
                    anchorX = calloutX + boxW;
                } else {
                    // Default: left of pin
                    calloutX = Math.max(20, x - boxW - 80);
                    calloutY = Math.max(20, y - boxH / 2);
                    anchorX = calloutX + boxW;
                }
            }

            const connector = showCallout
                ? `<line x1="${anchorX}" y1="${calloutY + 18}" x2="${x}" y2="${y - 6}"
                       stroke="${c.calloutBorder}" stroke-width="1.2" opacity="0.7"/>`
                : "";

            const calloutSvg = showCallout
                ? `<g transform="translate(${calloutX} ${calloutY})" filter="url(#calloutShadow)">
                    <rect x="0" y="0" width="${boxW}" height="${boxH}" rx="6"
                          fill="${c.calloutBg}" stroke="${c.calloutBorder}" stroke-width="1.2"/>
                    <rect x="0" y="0" width="4" height="${boxH}" rx="2" fill="${color}"/>
                    <!-- Building icon -->
                    <g transform="translate(14 10)">
                        <rect x="0" y="2" width="22" height="34" rx="1" fill="none" stroke="${c.accent}" stroke-width="1.4"/>
                        <rect x="3" y="6" width="3" height="3" fill="${c.accent}"/>
                        <rect x="9" y="6" width="3" height="3" fill="${c.accent}"/>
                        <rect x="15" y="6" width="3" height="3" fill="${c.accent}"/>
                        <rect x="3" y="12" width="3" height="3" fill="${c.accent}" opacity="0.7"/>
                        <rect x="9" y="12" width="3" height="3" fill="${c.accent}" opacity="0.7"/>
                        <rect x="15" y="12" width="3" height="3" fill="${c.accent}" opacity="0.7"/>
                        <rect x="3" y="18" width="3" height="3" fill="${c.accent}" opacity="0.5"/>
                        <rect x="9" y="18" width="3" height="3" fill="${c.accent}" opacity="0.5"/>
                        <rect x="15" y="18" width="3" height="3" fill="${c.accent}" opacity="0.5"/>
                        <rect x="3" y="24" width="3" height="3" fill="${c.accent}" opacity="0.4"/>
                        <rect x="9" y="24" width="3" height="3" fill="${c.accent}" opacity="0.4"/>
                        <rect x="15" y="24" width="3" height="3" fill="${c.accent}" opacity="0.4"/>
                    </g>
                    <!-- Project name + city -->
                    <text x="46" y="26" font-size="13" font-weight="700"
                          font-family="'Plus Jakarta Sans', sans-serif" fill="${c.textStrong}">${this._escapeXml(pin.names[0] || pin.city)}</text>
                    <text x="46" y="44" font-size="11" font-weight="700"
                          font-family="'Plus Jakarta Sans', sans-serif" fill="${c.accent}" letter-spacing="1.5">${this._escapeXml(pin.city)}</text>
                </g>`
                : "";

            return `
                <g class="sgc-map-pin">
                    <circle cx="${x}" cy="${y}" r="14" fill="${color}" opacity="0.18">
                        <animate attributeName="r" values="14;28;14" dur="2.6s" begin="${delay}s" repeatCount="indefinite"/>
                        <animate attributeName="opacity" values="0.35;0;0.35" dur="2.6s" begin="${delay}s" repeatCount="indefinite"/>
                    </circle>
                    <circle cx="${x}" cy="${y}" r="11" fill="${color}" opacity="0.25"/>
                    <circle cx="${x}" cy="${y}" r="7" fill="${color}" stroke="white" stroke-width="2.5"/>
                    <circle cx="${x}" cy="${y}" r="3" fill="white"/>
                </g>
                ${connector}
                ${calloutSvg}`;
        }).join("\n");

        /* Compass rose - top-left, ornate with N/S/E/W */
        const compass = `
            <g transform="translate(56 56)" filter="url(#calloutShadow)">
                <circle r="32" fill="${c.calloutBg}" stroke="${c.calloutBorder}" stroke-width="1.4"/>
                <circle r="26" fill="none" stroke="${c.accent}" stroke-width="0.5" opacity="0.5"/>
                <text x="0" y="-16" text-anchor="middle" font-size="13" font-weight="800"
                      fill="${c.textStrong}" font-family="'Plus Jakarta Sans', sans-serif">N</text>
                <text x="0" y="22" text-anchor="middle" font-size="11" font-weight="700"
                      fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">S</text>
                <text x="-19" y="5" text-anchor="middle" font-size="11" font-weight="700"
                      fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">W</text>
                <text x="19" y="5" text-anchor="middle" font-size="11" font-weight="700"
                      fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">E</text>
                <!-- 4-point compass star -->
                <path d="M 0 -22 L 4 0 L 0 -2 L -4 0 Z" fill="${c.accent}"/>
                <path d="M 0 22 L 4 0 L 0 2 L -4 0 Z" fill="${c.text}" opacity="0.6"/>
                <path d="M 22 0 L 0 4 L -2 0 L 0 -4 Z" fill="${c.text}" opacity="0.4"/>
                <path d="M -22 0 L 0 4 L 2 0 L 0 -4 Z" fill="${c.text}" opacity="0.4"/>
                <circle r="2" fill="${c.accent}"/>
            </g>`;

        /* Scale bar - bottom-left */
        const scale = (() => {
            const x = 32, y = H - 40;
            const kmPerDeg = 111;
            const segDeg = 0.5;
            const segPx = ((segDeg) / (maxLon - minLon)) * W;
            const segments = 4;
            let bars = "";
            for (let i = 0; i < segments; i++) {
                const fill = i % 2 === 0 ? c.textStrong : "transparent";
                bars += `<rect x="${x + i * segPx}" y="${y - 5}" width="${segPx}" height="7" fill="${fill}" stroke="${c.textStrong}" stroke-width="0.8"/>`;
            }
            const labels = [];
            for (let i = 0; i <= segments; i++) {
                labels.push(`<text x="${x + i * segPx}" y="${y + 18}" text-anchor="middle" font-size="11" font-weight="600" fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">${Math.round(i * segDeg * kmPerDeg)}</text>`);
            }
            return `<g>${bars}${labels.join("")}<text x="${x}" y="${y - 12}" font-size="11" font-weight="600" fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">km</text></g>`;
        })();

        /* Status Legend - bottom-right (matches reference) */
        const statusLegend = `
            <g transform="translate(${W - 56} ${H - 230})">
                <rect x="-220" y="0" width="220" height="200" rx="12"
                      fill="${c.calloutBg}" stroke="${c.calloutBorder}" stroke-width="1.4"
                      filter="url(#calloutShadow)"/>
                <text x="-204" y="28" font-size="13" font-weight="800"
                      fill="${c.accent}" font-family="'Plus Jakarta Sans', sans-serif"
                      letter-spacing="2.5">STATUS LEGEND</text>
                <line x1="-204" y1="42" x2="-16" y2="42" stroke="${c.accent}" stroke-width="1" opacity="0.5"/>
                <g transform="translate(-200 70)">
                    <circle cx="0" cy="0" r="8" fill="${c.statusGreen}"/>
                    <text x="18" y="0" font-size="13" font-weight="700"
                          fill="${c.statusGreen}" font-family="'Plus Jakarta Sans', sans-serif" letter-spacing="1">ON TRACK</text>
                    <text x="18" y="16" font-size="10" font-weight="500"
                          fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">Projects on schedule</text>
                </g>
                <g transform="translate(-200 118)">
                    <circle cx="0" cy="0" r="8" fill="${c.statusAmber}"/>
                    <text x="18" y="0" font-size="13" font-weight="700"
                          fill="${c.statusAmber}" font-family="'Plus Jakarta Sans', sans-serif" letter-spacing="1">WARNING</text>
                    <text x="18" y="16" font-size="10" font-weight="500"
                          fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">Projects at risk</text>
                </g>
                <g transform="translate(-200 166)">
                    <circle cx="0" cy="0" r="8" fill="${c.statusRed}"/>
                    <text x="18" y="0" font-size="13" font-weight="700"
                          fill="${c.statusRed}" font-family="'Plus Jakarta Sans', sans-serif" letter-spacing="1">CRITICAL</text>
                    <text x="18" y="16" font-size="10" font-weight="500"
                          fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">Projects requiring</text>
                    <text x="18" y="28" font-size="10" font-weight="500"
                          fill="${c.text}" font-family="'Plus Jakarta Sans', sans-serif">immediate attention</text>
                </g>
            </g>`;

        return `
        <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"
             preserveAspectRatio="xMidYMid meet"
             style="width:100%; height:100%; display:block;">
            <defs>
                <linearGradient id="uaeOceanGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="${c.ocean1}"/>
                    <stop offset="50%" stop-color="${c.ocean2}"/>
                    <stop offset="100%" stop-color="${c.ocean3}"/>
                </linearGradient>
                <linearGradient id="uaeLandGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="${c.land1}"/>
                    <stop offset="100%" stop-color="${c.land2}"/>
                </linearGradient>
                <linearGradient id="neighborGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="${c.neighborFill}"/>
                    <stop offset="100%" stop-color="${c.neighborFill}" stop-opacity="0.85"/>
                </linearGradient>
                <radialGradient id="uaeVignette" cx="50%" cy="50%" r="65%">
                    <stop offset="65%" stop-color="${c.ocean2}" stop-opacity="0"/>
                    <stop offset="100%" stop-color="#000" stop-opacity="0.18"/>
                </radialGradient>
                <filter id="calloutShadow" x="-50%" y="-50%" width="200%" height="200%">
                    <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="${c.calloutShadow}" flood-opacity="0.5"/>
                </filter>
            </defs>
            <!-- Ocean base -->
            <rect x="0" y="0" width="${W}" height="${H}" fill="url(#uaeOceanGrad)"/>
            <!-- Graticule -->
            ${grid.join("")}
            ${axisLabels.join("")}
            <!-- Neighbor countries (subtle context) -->
            <path d="${pathFromCoords(saudiCoast)}" fill="url(#neighborGrad)" stroke="${c.neighborStroke}" stroke-width="1" opacity="0.85"/>
            <path d="${pathFromCoords(omanCoast)}" fill="url(#neighborGrad)" stroke="${c.neighborStroke}" stroke-width="1" opacity="0.85"/>
            <path d="${pathFromCoords(qatarStub)}" fill="url(#neighborGrad)" stroke="${c.neighborStroke}" stroke-width="1" opacity="0.85"/>
            <path d="${pathFromCoords(iranStub)}" fill="url(#neighborGrad)" stroke="${c.neighborStroke}" stroke-width="1" opacity="0.85"/>
            <!-- Country labels -->
            <text x="${proj(51.2, 26.5).x}" y="${proj(51.2, 26.5).y}" font-size="14" font-weight="700"
                  fill="${c.neighborText}" font-family="'Plus Jakarta Sans', sans-serif"
                  letter-spacing="3" opacity="0.7">SAUDI ARABIA</text>
            <text x="${proj(56.85, 23.5).x}" y="${proj(56.85, 23.5).y}" font-size="14" font-weight="700"
                  fill="${c.neighborText}" font-family="'Plus Jakarta Sans', sans-serif"
                  letter-spacing="3" opacity="0.7">OMAN</text>
            <text x="${proj(50.9, 25.0).x}" y="${proj(50.9, 25.0).y}" font-size="11" font-weight="700"
                  fill="${c.neighborText}" font-family="'Plus Jakarta Sans', sans-serif"
                  letter-spacing="2" opacity="0.6">QATAR</text>
            <!-- PERSIAN GULF label -->
            ${persianGulfLabel}
            <!-- UAE mainland (with gold border) -->
            <path d="${uaePath}" fill="url(#uaeLandGrad)" stroke="${c.landStroke}" stroke-width="1.8" stroke-linejoin="round"/>
            <!-- UAE Islands -->
            ${islandPaths ? `<g fill="url(#uaeLandGrad)" stroke="${c.landStroke}" stroke-width="1.2">${islandPaths}</g>` : ""}
            <!-- City labels -->
            ${cityLabels}
            <!-- Project pins + callouts -->
            ${pinSvg}
            <!-- Vignette overlay -->
            <rect x="0" y="0" width="${W}" height="${H}" fill="url(#uaeVignette)" pointer-events="none"/>
            <!-- UI overlays -->
            ${compass}
            ${scale}
            ${statusLegend}
        </svg>`;
    }

    _escapeXml(s) {
        return String(s || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    _worstRag(projects) {
        const order = { red: 3, orange: 2, amber: 1, green: 0 };
        let worst = "green";
        for (const p of projects) {
            const s = p.rag_status || "green";
            if ((order[s] || 0) > (order[worst] || 0)) worst = s;
        }
        return worst;
    }

    /* ----------------------------- CHARTS ----------------------------- */
    renderHealthMatrix() {
        if (!this.healthMatrixRef.el || !window.echarts) {
            setTimeout(() => this.renderHealthMatrix(), 200);
            return;
        }

        const dark = this.state.theme === "dark";
        const projects = this.state.projects || [];
        const statusColor = {
            green: dark ? "#22c55e" : "#10b981",
            amber: dark ? "#fbbf24" : "#f59e0b",
            orange: dark ? "#fb923c" : "#f97316",
            red: dark ? "#f87171" : "#ef4444",
            blue: dark ? "#60a5fa" : "#3b82f6",
        };

        const series = Object.keys(statusColor).map((status) => ({
            name: status.charAt(0).toUpperCase() + status.slice(1),
            type: "scatter",
            symbolSize: 28,
            itemStyle: { color: statusColor[status], opacity: 0.9, borderColor: dark ? "#0d1426" : "#ffffff", borderWidth: 2 },
            data: projects
                .filter((p) => (p.rag_status || "blue") === status)
                .map((p) => ({
                    name: p.name,
                    value: [
                        Math.max(-20, Math.min(20, (p.progress || 0) - (p.planned_progress || 0))),
                        Math.max(-20, Math.min(20, (p.budget_consumed || 0) - 100)),
                    ],
                })),
        }));

        const chart = window.echarts.init(this.healthMatrixRef.el, null, { renderer: "canvas" });
        chart.setOption({
            grid: { left: 56, right: 32, top: 32, bottom: 48 },
            tooltip: {
                trigger: "item",
                backgroundColor: dark ? "#131b35" : "#ffffff",
                borderColor: dark ? "#243157" : "#d6dae6",
                textStyle: { color: dark ? "#f1f5f9" : "#0f172a", fontFamily: "Plus Jakarta Sans" },
                formatter: (p) => `<strong>${p.data.name}</strong><br/>Cost Δ ${p.value[1].toFixed(1)}% &nbsp; Schedule Δ ${p.value[0].toFixed(1)}%`,
            },
            legend: { show: false },
            xAxis: {
                type: "value",
                name: "Schedule Performance",
                nameLocation: "middle",
                nameGap: 28,
                nameTextStyle: { color: dark ? "#64748b" : "#94a3b8", fontSize: 10, fontWeight: 600 },
                min: -20, max: 20,
                splitLine: { lineStyle: { color: dark ? "#1c2645" : "#e6e9f2", type: "dashed" } },
                axisLine: { show: false },
                axisLabel: { color: dark ? "#94a3b8" : "#64748b", fontSize: 10, formatter: "{value}%" },
                axisTick: { show: false },
            },
            yAxis: {
                type: "value",
                name: "Cost Performance",
                nameLocation: "middle",
                nameGap: 40,
                nameTextStyle: { color: dark ? "#64748b" : "#94a3b8", fontSize: 10, fontWeight: 600 },
                min: -20, max: 20,
                splitLine: { lineStyle: { color: dark ? "#1c2645" : "#e6e9f2", type: "dashed" } },
                axisLine: { show: false },
                axisLabel: { color: dark ? "#94a3b8" : "#64748b", fontSize: 10, formatter: "{value}%" },
                axisTick: { show: false },
            },
            series: series.filter((s) => s.data.length > 0),
        });

        // Mark zones (quadrant labels) via graphic
        const labels = [
            { top: "8%", left: "16%", text: "COST OVER / AHEAD OF SCHEDULE", color: dark ? "#fbbf24" : "#f59e0b" },
            { top: "8%", right: "16%", text: "COST UNDER / AHEAD OF SCHEDULE", color: dark ? "#22c55e" : "#10b981" },
            { bottom: "8%", left: "16%", text: "COST OVER / BEHIND SCHEDULE", color: dark ? "#f87171" : "#ef4444" },
            { bottom: "8%", right: "16%", text: "COST UNDER / BEHIND SCHEDULE", color: dark ? "#fb923c" : "#f97316" },
        ];
        const graphics = labels.map((l) => ({
            type: "text",
            ...l,
            style: { text: l.text, fill: l.color, fontSize: 9, fontWeight: 700, fontFamily: "Plus Jakarta Sans" },
        }));
        chart.setOption({ graphic: graphics });

        this._healthChart = chart;
        this._resizeHealth = () => chart.resize();
        window.addEventListener("resize", this._resizeHealth);
    }

    renderFinancialChart() {
        if (!this.financialChartRef.el || !window.echarts) {
            setTimeout(() => this.renderFinancialChart(), 200);
            return;
        }

        const dark = this.state.theme === "dark";
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

        // Synthesized demo data scaled to current revenue/cost totals
        const totalRev = this.state.total_revenue || 0;
        const totalCost = this.state.total_costs || 0;
        const monthlyRev = Array(12).fill(0).map((_, i) => Math.round((totalRev / 12) * (0.7 + Math.sin(i) * 0.2 + i * 0.05)));
        const monthlyCost = Array(12).fill(0).map((_, i) => Math.round((totalCost / 12) * (0.6 + Math.cos(i) * 0.15 + i * 0.04)));
        const monthlyProfit = monthlyRev.map((r, i) => r - monthlyCost[i]);

        const chart = window.echarts.init(this.financialChartRef.el, null, { renderer: "canvas" });
        chart.setOption({
            grid: { left: 56, right: 56, top: 32, bottom: 32 },
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                backgroundColor: dark ? "#131b35" : "#ffffff",
                borderColor: dark ? "#243157" : "#d6dae6",
                textStyle: { color: dark ? "#f1f5f9" : "#0f172a", fontFamily: "Plus Jakarta Sans" },
                formatter: (params) => {
                    const lines = params.map((p) =>
                        `${p.marker} ${p.seriesName}: <strong>${this.formatCurrency(p.value)}</strong>`
                    );
                    return `<strong>${params[0].axisValue}</strong><br/>` + lines.join("<br/>");
                },
            },
            legend: {
                data: ["Revenue", "Cost", "Net Profit"],
                bottom: 0,
                textStyle: { color: dark ? "#94a3b8" : "#475569", fontFamily: "Plus Jakarta Sans", fontSize: 11 },
                icon: "roundRect",
                itemWidth: 10,
                itemHeight: 10,
            },
            xAxis: {
                type: "category",
                data: months,
                axisLine: { lineStyle: { color: dark ? "#243157" : "#d6dae6" } },
                axisLabel: { color: dark ? "#94a3b8" : "#64748b", fontSize: 10 },
                axisTick: { show: false },
            },
            yAxis: [
                {
                    type: "value",
                    name: "AED (M)",
                    nameTextStyle: { color: dark ? "#64748b" : "#94a3b8", fontSize: 10 },
                    axisLabel: {
                        color: dark ? "#94a3b8" : "#64748b",
                        fontSize: 10,
                        formatter: (v) => `${(v / 1000000).toFixed(0)}M`,
                    },
                    splitLine: { lineStyle: { color: dark ? "#1c2645" : "#eef0f6", type: "dashed" } },
                },
                {
                    type: "value",
                    name: "Profit",
                    nameTextStyle: { color: dark ? "#64748b" : "#94a3b8", fontSize: 10 },
                    axisLabel: { color: dark ? "#94a3b8" : "#64748b", fontSize: 10, formatter: (v) => `${(v / 1000000).toFixed(0)}M` },
                    splitLine: { show: false },
                },
            ],
            series: [
                {
                    name: "Revenue",
                    type: "bar",
                    data: monthlyRev,
                    itemStyle: { color: dark ? "#60a5fa" : "#1e40af", borderRadius: [4, 4, 0, 0] },
                    barGap: "20%",
                },
                {
                    name: "Cost",
                    type: "bar",
                    data: monthlyCost,
                    itemStyle: { color: dark ? "#fbbf24" : "#f59e0b", borderRadius: [4, 4, 0, 0] },
                },
                {
                    name: "Net Profit",
                    type: "line",
                    yAxisIndex: 1,
                    data: monthlyProfit,
                    smooth: true,
                    symbol: "circle",
                    symbolSize: 6,
                    lineStyle: { color: dark ? "#22c55e" : "#10b981", width: 3 },
                    itemStyle: { color: dark ? "#22c55e" : "#10b981", borderColor: dark ? "#0d1426" : "#ffffff", borderWidth: 2 },
                },
            ],
        });

        this._financialChart = chart;
        this._resizeFin = () => chart.resize();
        window.addEventListener("resize", this._resizeFin);
    }

    /* ----------------------------- ACTIONS ----------------------------- */
    toggleTheme() {
        const next = this.state.theme === "light" ? "dark" : "light";
        this.state.theme = next;
        document.documentElement.setAttribute("data-theme", next);
        try {
            window.localStorage.setItem(THEME_KEY, next);
        } catch (_) {}
        // Re-render charts so they pick up new colors
        setTimeout(() => {
            this.renderHealthMatrix();
            this.renderFinancialChart();
            this.renderMap(); // Leaflet uses different tiles per theme
        }, 0);
    }

    setFinancialPeriod(period) {
        this.state.financial_period = period;
        this.renderFinancialChart();
    }

    /* ----------------------------- FORMATTERS ----------------------------- */
    formatCurrency(amount) {
        const sym = this.state.currency_symbol || "";
        return sym + " " + this._formatAmount(amount, 2);
    }

    formatCompact(amount) {
        const sym = this.state.currency_symbol || "";
        return sym + " " + this._formatAmount(amount, 1);
    }

    formatMoney(amount) {
        const sym = this.state.currency_symbol || "";
        return sym + " " + this._formatAmount(amount, 1);
    }

    _formatAmount(amount, bigPrecision) {
        if (amount === null || amount === undefined || amount === "") return "0";
        const n = Number(amount);
        if (Number.isNaN(n)) return "0";
        const abs = Math.abs(n);
        if (abs >= 1_000_000_000) return (n / 1_000_000_000).toFixed(bigPrecision) + "B";
        if (abs >= 1_000_000) return (n / 1_000_000).toFixed(bigPrecision) + "M";
        if (abs >= 1_000) return (n / 1_000).toFixed(1) + "K";
        return n.toLocaleString("en-US");
    }

    get receivables_label() {
        return this.formatCompact(this.state.receivables);
    }
}

registry.category("actions").add("construction_dashboard", ConstructionDashboard);