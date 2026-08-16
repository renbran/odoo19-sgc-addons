/* =====================================================================
   CRM Executive Dashboard — Vanilla JS Renderer
   =====================================================================
   Zero-dependency dashboard renderer. No Owl, no publicWidget, no
   module imports — just fetch() + DOM. Works in any Odoo asset
   bundle (backend, frontend, public) because it uses only APIs
   that exist in every modern browser.

   What it does
   ------------
   1. On DOMContentLoaded, reads the filter from the #ced-root data-*
      attributes (rendered server-side by the QWeb template).
   2. Calls GET /crm-dashboard/data with the current filter.
   3. Renders the 8 sections as plain HTML inside the root.
   4. Wires up the period <select> and refresh button to refetch.
   5. On error, shows a clean error banner with a reload button.
   ===================================================================== */

(function () {
    "use strict";

    // ------------------------------------------------------------------
    // Helpers — all pure, no closures
    // ------------------------------------------------------------------

    function escapeHtml(s) {
        if (s == null) return "";
        return String(s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function formatNumber(n) {
        if (n == null || isNaN(n)) return "—";
        return new Intl.NumberFormat("en-US").format(n);
    }

    function formatCurrency(n) {
        if (n == null || isNaN(n)) return "—";
        return "$" + new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(n);
    }

    function formatPercent(n) {
        if (n == null || isNaN(n)) return "—";
        return Number(n).toFixed(1) + "%";
    }

    function getCsrfToken() {
        // Odoo exposes the CSRF token via a meta tag or the odoo global.
        var token = "";
        if (typeof window.odoo !== "undefined" && window.odoo.csrf_token) {
            token = window.odoo.csrf_token;
        }
        if (!token) {
            var meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) token = meta.getAttribute("content");
        }
        if (!token) {
            // Fallback: read from cookie
            var m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
            if (m) token = decodeURIComponent(m[1]);
        }
        return token;
    }

    // ------------------------------------------------------------------
    // Drill-down — click a card/row/chart segment to see the records
    // behind the number.
    // ------------------------------------------------------------------

    function drillAttrs(type, key) {
        // Emitted on any clickable element. `key` may be an id, a
        // string, or null (e.g. "Undefined" source bucket).
        return ' data-drill-type="' + escapeHtml(type) + '"' +
            ' data-drill-key="' + (key === null || key === undefined ? "" : escapeHtml(String(key))) + '"' +
            ' role="button" tabindex="0"';
    }

    function openDrilldown(drillType, drillKey, filter) {
        fetch("/crm-dashboard/drilldown", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": getCsrfToken(),
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { drill_type: drillType, drill_key: drillKey, filter: filter },
                id: Math.floor(Math.random() * 1000000),
            }),
        }).then(function (resp) {
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            return resp.json();
        }).then(function (data) {
            if (data && data.error) throw new Error(data.error.message || "Drill-down failed");
            var r = data && data.result;
            if (!r || r.ok === false) throw new Error((r && r.error) || "Nothing to show");
            var action = r.payload;
            var domainStr = encodeURIComponent(JSON.stringify(action.domain || []));
            var url = "/web#model=" + encodeURIComponent(action.res_model) +
                "&view_type=list&domain=" + domainStr +
                "&action_name=" + encodeURIComponent(action.name || "");
            window.open(url, "_blank");
        }).catch(function (err) {
            console.error("CED: drilldown failed", err);
        });
    }

    function wireDrilldowns(rootEl, filter) {
        function trigger(el) {
            var type = el.getAttribute("data-drill-type");
            var key = el.getAttribute("data-drill-key");
            if (!type) return;
            openDrilldown(type, key === "" ? null : key, filter);
        }
        rootEl.addEventListener("click", function (ev) {
            var el = ev.target.closest("[data-drill-type]");
            if (el && rootEl.contains(el)) trigger(el);
        });
        rootEl.addEventListener("keydown", function (ev) {
            if (ev.key !== "Enter" && ev.key !== " ") return;
            var el = ev.target.closest("[data-drill-type]");
            if (el && rootEl.contains(el)) {
                ev.preventDefault();
                trigger(el);
            }
        });
    }

    // ------------------------------------------------------------------
    // Section renderers — each returns an HTML string
    // ------------------------------------------------------------------

    function renderHeader(rootEl, filter, payload) {
        var generatedAt = payload && payload.generated_at
            ? new Date(payload.generated_at).toLocaleString()
            : "—";
        return (
            '<div class="ced-dashboard">' +
            '<header class="ced-dashboard__header">' +
            '<h1 class="ced-dashboard__title">' +
            '<i class="fa fa-tachometer-alt"></i> CRM Executive Dashboard' +
            '</h1>' +
            '<div class="ced-dashboard__filter">' +
            '<span class="ced-filter__label">Period:</span>' +
            '<select id="ced-period" class="ced-filter__select">' +
            renderPeriodOptions(filter.period) +
            '</select>' +
            '<span class="ced-filter__label">Saved:</span>' +
            '<select id="ced-saved-filter" class="ced-filter__select">' +
            '<option value="">— Choose a saved filter —</option>' +
            '</select>' +
            '<button id="ced-save-filter" class="ced-btn ced-btn--secondary" title="Save current filter">' +
            '<i class="fa fa-bookmark"></i> Save' +
            '</button>' +
            '<button id="ced-refresh" class="ced-btn ced-btn--gold">' +
            '<i class="fa fa-sync"></i> Refresh' +
            '</button>' +
            '<span class="ced-filter__updated">Updated: ' + escapeHtml(generatedAt) + '</span>' +
            '</div>' +
            '</header>'
        );
    }

    function renderPeriodOptions(selected) {
        var opts = [
            ["today", "Today"],
            ["yesterday", "Yesterday"],
            ["last_7_days", "Last 7 Days"],
            ["last_30_days", "Last 30 Days"],
            ["last_90_days", "Last 90 Days"],
            ["current_month", "Current Month"],
            ["current_quarter", "Current Quarter"],
            ["current_year", "Current Year"],
        ];
        return opts.map(function (o) {
            var sel = o[0] === selected ? ' selected="selected"' : "";
            return '<option value="' + o[0] + '"' + sel + '>' + o[1] + '</option>';
        }).join("");
    }

    function renderKpiCard(title, value, icon, level, format, drillKey) {
        var fmt = format || "number";
        var v;
        if (fmt === "currency") v = formatCurrency(value);
        else if (fmt === "percent") v = formatPercent(value);
        else v = formatNumber(value);
        var clickable = drillKey ? " ced-kpi-card--clickable" : "";
        var attrs = drillKey ? drillAttrs("kpi", drillKey) : "";
        return (
            '<div class="ced-kpi-card ced-kpi-card--' + (level || "default") + clickable + '"' + attrs + '>' +
            '<div class="ced-kpi-card__icon"><i class="fa ' + escapeHtml(icon) + '"></i></div>' +
            '<div class="ced-kpi-card__body">' +
            '<div class="ced-kpi-card__title">' + escapeHtml(title) + '</div>' +
            '<div class="ced-kpi-card__value">' + v + '</div>' +
            '</div>' +
            '</div>'
        );
    }

    function renderKpiOverview(kpi) {
        var cards = [
            renderKpiCard("Total Leads", kpi.leads.total, "fa-user-plus", "default", "number", "leads_total"),
            renderKpiCard("New Today", kpi.leads.new_today, "fa-user-clock", "info", "number", "leads_new_today"),
            renderKpiCard("New This Week", kpi.leads.new_week, "fa-calendar-week", "default", "number", "leads_new_week"),
            renderKpiCard("New This Month", kpi.leads.new_month, "fa-calendar-alt", "default", "number", "leads_new_month"),
            renderKpiCard("Qualified", kpi.leads.qualified, "fa-user-check", "success", "number", "leads_qualified"),
            renderKpiCard("Open Opps", kpi.opportunities.open, "fa-briefcase", "info", "number", "opps_open"),
            renderKpiCard("Won", kpi.opportunities.won, "fa-trophy", "success", "number", "opps_won"),
            renderKpiCard("Lost", kpi.opportunities.lost, "fa-times-circle", "danger", "number", "opps_lost"),
            renderKpiCard("Pipeline", kpi.revenue.pipeline_value, "fa-money-bill-wave", "gold", "currency", "revenue_pipeline"),
            renderKpiCard("Forecast", kpi.revenue.forecast, "fa-chart-line", "gold", "currency", "revenue_pipeline"),
            renderKpiCard("Won Revenue", kpi.revenue.won, "fa-dollar-sign", "success", "currency", "revenue_won"),
            renderKpiCard("Lead Conv.", kpi.conversion.lead_conversion_rate, "fa-percentage", "info", "percent"),
            renderKpiCard("Win Rate", kpi.conversion.opp_win_rate, "fa-trophy", "success", "percent"),
            renderKpiCard("Avg Conv. (days)", kpi.conversion.avg_conversion_days, "fa-clock", "default", "number"),
        ];
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Executive KPI Overview</h2>' +
            '<div class="ced-kpi-grid">' + cards.join("") + '</div>' +
            '</section>'
        );
    }

    function renderAlerts(alerts) {
        if (!alerts || !alerts.length) {
            return (
                '<section class="ced-section">' +
                '<h2 class="ced-section__title">Executive Alert Center</h2>' +
                '<div class="ced-empty-state">No alerts</div>' +
                '</section>'
            );
        }
        var html = alerts.map(function (a) {
            return (
                '<div class="ced-alert ced-alert--' + escapeHtml(a.level || "info") + '">' +
                '<div class="ced-alert__icon"><i class="fa ' + escapeHtml(a.icon || "fa-info-circle") + '"></i></div>' +
                '<div class="ced-alert__body">' +
                '<div class="ced-alert__title">' + escapeHtml(a.title) + '</div>' +
                '<div class="ced-alert__message">' + escapeHtml(a.message) + '</div>' +
                '</div>' +
                '</div>'
            );
        }).join("");
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Executive Alert Center</h2>' +
            '<div class="ced-alerts-grid">' + html + '</div>' +
            '</section>'
        );
    }

    function renderProductivity(prod) {
        if (!prod || !prod.users || !prod.users.length) {
            return (
                '<section class="ced-section">' +
                '<h2 class="ced-section__title">Productivity Dashboard</h2>' +
                '<div class="ced-empty-state">No productivity data</div>' +
                '</section>'
            );
        }
        var top = prod.users.slice(0, 5);
        var rows = top.map(function (u) {
            return (
                '<tr>' +
                '<td>' + escapeHtml(u.name) + '</td>' +
                '<td>' + formatNumber(u.leads_assigned) + '</td>' +
                '<td>' + formatNumber(u.activities_completed) + '</td>' +
                '<td>' + formatPercent(u.conversion_rate) + '</td>' +
                '<td>' + formatCurrency(u.revenue_generated) + '</td>' +
                '</tr>'
            );
        }).join("");
        var k = prod.kpis || {};
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Productivity Dashboard</h2>' +
            '<div class="ced-productivity-grid">' +
            '<div class="ced-productivity-card">' +
            '<h3>Top Salespeople</h3>' +
            '<table>' +
            '<thead><tr><th>Name</th><th>Leads</th><th>Activities</th><th>Conv.</th><th>Revenue</th></tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
            '</table>' +
            '</div>' +
            '<div class="ced-productivity-card">' +
            '<h3>Productivity KPIs</h3>' +
            '<table>' +
            '<tr><td>Leads per day</td><td>' + formatNumber(k.leads_per_day) + '</td></tr>' +
            '<tr><td>Activities per day</td><td>' + formatNumber(k.activities_per_day) + '</td></tr>' +
            '<tr><td>Revenue per employee</td><td>' + formatCurrency(k.revenue_per_employee) + '</td></tr>' +
            '<tr><td>Revenue per opportunity</td><td>' + formatCurrency(k.revenue_per_opp) + '</td></tr>' +
            '<tr><td>Activities per deal</td><td>' + formatNumber(k.activities_per_deal) + '</td></tr>' +
            '</table>' +
            '</div>' +
            '</div>' +
            '</section>'
        );
    }

    function renderStartup(s) {
        if (!s) return "";
        var h = s.business_health || {};
        var g = s.growth || {};
        var r = s.risk || {};
        var p = s.pipeline_health || {};
        var ds = h.days_since_booking;
        var dsStr = ds == null ? "—" : formatNumber(ds) + " days";
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Startup Executive Metrics</h2>' +
            '<div class="ced-kpi-grid">' +
            renderKpiCard("Days Since Last Booking", ds, "fa-calendar-times-o",
                ds != null && ds > 7 ? "warning" : "success", "number") +
            renderKpiCard("Stale Opps", r.stagnant_opps, "fa-hourglass-half", "warning", "number", "stale_opps") +
            renderKpiCard("Overdue Follow-ups", r.overdue_followups, "fa-exclamation-triangle", "danger", "number", "overdue_followups") +
            renderKpiCard("Pipeline Coverage", p.coverage_ratio, "fa-shield-alt", "info", "number") +
            renderKpiCard("Weekly Lead Growth", g.weekly_growth, "fa-chart-line", "info", "percent") +
            renderKpiCard("Revenue Growth", g.revenue_growth, "fa-dollar-sign", "success", "percent") +
            '</div>' +
            '</section>'
        );
    }

    function renderOwnerBreakdown(oa) {
        if (!oa || !oa.owners || !oa.owners.length) return "";
        var rows = oa.owners.slice(0, 10).map(function (o) {
            return (
                '<tr class="ced-row--clickable"' + drillAttrs("owner", o.user_id) + '>' +
                '<td>' + escapeHtml(o.name) + '</td>' +
                '<td>' + formatNumber(o.opportunities) + '</td>' +
                '<td>' + formatCurrency(o.pipeline_value) + '</td>' +
                '<td>' + formatNumber(o.won) + '</td>' +
                '<td>' + formatPercent(o.win_rate) + '</td>' +
                '</tr>'
            );
        }).join("");
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Pipeline by Owner</h2>' +
            '<div class="ced-leads-card">' +
            '<table>' +
            '<thead><tr><th>Owner</th><th>Opportunities</th><th>Pipeline</th><th>Won</th><th>Win Rate</th></tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
            '</table>' +
            '</div>' +
            '</section>'
        );
    }

    function renderCampaignAnalytics(ca) {
        if (!ca) return "";
        var sources = ca.sources || [];
        var campaigns = ca.campaigns || [];

        var sourceRows = sources.map(function (s) {
            return (
                '<tr class="ced-row--clickable"' + drillAttrs("source", s.source_id) + '>' +
                '<td>' + escapeHtml(s.name) + '</td>' +
                '<td>' + formatNumber(s.count) + '</td>' +
                '<td>' + formatPercent(s.share) + '</td>' +
                '<td>' + formatNumber(s.won) + '</td>' +
                '</tr>'
            );
        }).join("");

        var campaignRows = campaigns.map(function (c) {
            var roiStr = c.roi === null || c.roi === undefined ? "—" : formatPercent(c.roi);
            var roiClass = c.roi == null ? "" : (c.roi >= 0 ? "ced-text--success" : "ced-text--danger");
            return (
                '<tr class="ced-row--clickable"' + drillAttrs("campaign", c.campaign_id) + '>' +
                '<td>' + escapeHtml(c.name) + '</td>' +
                '<td>' + formatNumber(c.leads) + '</td>' +
                '<td>' + formatCurrency(c.won_revenue) + '</td>' +
                '<td>' + formatCurrency(c.budget) + '</td>' +
                '<td class="' + roiClass + '">' + roiStr + '</td>' +
                '</tr>'
            );
        }).join("");

        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Campaign, Source &amp; ROI</h2>' +
            '<div class="ced-productivity-grid">' +
            '<div class="ced-productivity-card">' +
            '<h3>Source of Leads</h3>' +
            (sourceRows ?
                '<table>' +
                '<thead><tr><th>Source</th><th>Leads</th><th>Share</th><th>Won</th></tr></thead>' +
                '<tbody>' + sourceRows + '</tbody>' +
                '</table>' : '<div class="ced-empty-state">No source data</div>') +
            '</div>' +
            '<div class="ced-productivity-card">' +
            '<h3>Campaign Performance &amp; ROI</h3>' +
            (campaignRows ?
                '<table>' +
                '<thead><tr><th>Campaign</th><th>Leads</th><th>Won Revenue</th><th>Budget</th><th>ROI</th></tr></thead>' +
                '<tbody>' + campaignRows + '</tbody>' +
                '</table>' :
                '<div class="ced-empty-state">No campaigns with data for the current filter. ' +
                'Set a Budget on Marketing &gt; Campaigns to see ROI.</div>') +
            '</div>' +
            '</div>' +
            '</section>'
        );
    }

    function renderFunnel(funnel) {
        if (!funnel || !funnel.stages || !funnel.stages.length) return "";
        var max = 0;
        funnel.stages.forEach(function (s) { if (s.count > max) max = s.count; });
        var rows = funnel.stages.map(function (s) {
            var pct = max > 0 ? (s.count / max) * 100 : 0;
            var stageClass = s.is_won ? "ced-funnel__stage--won" : "";
            return (
                '<div class="ced-funnel__stage ced-funnel__stage--clickable ' + stageClass + '"' +
                drillAttrs("funnel_stage", s.stage_id) + '>' +
                '<div class="ced-funnel__stage-name">' + escapeHtml(s.name) + '</div>' +
                '<div class="ced-funnel__bar">' +
                '<div class="ced-funnel__bar-fill" style="width: ' + pct.toFixed(1) + '%"></div>' +
                '</div>' +
                '<div class="ced-funnel__count">' + formatNumber(s.count) + '</div>' +
                '<div class="ced-funnel__value">' + formatCurrency(s.value) + '</div>' +
                '</div>'
            );
        }).join("");
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Sales Funnel</h2>' +
            '<div class="ced-funnel">' + rows + '</div>' +
            '</section>'
        );
    }

    function renderDisposition(disp) {
        if (!disp) return "";
        var byStage = disp.by_stage || [];
        var rows = byStage.map(function (s) {
            var badge = s.is_entry ? "ced-alert--warning" : (s.is_won ? "ced-alert--success" : "ced-alert--info");
            return (
                '<tr>' +
                '<td>' + escapeHtml(s.name) +
                (s.is_entry ? ' <span class="badge ' + badge + '">untouched</span>' : '') +
                '</td>' +
                '<td>' + formatNumber(s.count) + '</td>' +
                '</tr>'
            );
        }).join("");
        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Disposition &amp; Engagement</h2>' +
            '<div class="ced-kpi-grid">' +
            renderKpiCard("Contact Rate", disp.contact_rate, "fa-phone", "info", "percent") +
            renderKpiCard("Worked This Period", disp.worked_period, "fa-hand-pointer-o", "success", "number") +
            renderKpiCard("Still Untouched (New)", disp.in_entry_stage, "fa-inbox",
                disp.in_entry_stage > 0 ? "warning" : "success", "number", "untouched") +
            renderKpiCard("Active Opportunities", disp.total_active, "fa-briefcase", "default", "number", "active_opps") +
            '</div>' +
            (rows ?
                '<div class="ced-leads-card">' +
                '<table>' +
                '<thead><tr><th>Current Stage</th><th>Count</th></tr></thead>' +
                '<tbody>' + rows + '</tbody>' +
                '</table>' +
                '</div>' : '') +
            '</section>'
        );
    }

    function renderError(message) {
        return (
            '<div class="ced-error-banner">' +
            '<i class="fa fa-exclamation-triangle"></i> ' +
            '<span>Dashboard error: ' + escapeHtml(message) + '</span>' +
            '<button id="ced-reload">Reload</button>' +
            '</div>'
        );
    }

    // ------------------------------------------------------------------
    // Charts — Chart.js loaded from CDN, no module imports
    // ------------------------------------------------------------------
    // The CDN script is loaded lazily on first chart render. If the
    // CDN is unreachable (offline, ad-blocker, CSP), we silently
    // fall back to the CSS-only data display — never break the page.

    var _chartJsLoading = null;
    var _chartJsLoaded = false;
    var _chartInstances = {};

    function loadChartJs() {
        if (_chartJsLoaded) return Promise.resolve();
        if (_chartJsLoading) return _chartJsLoading;
        _chartJsLoading = new Promise(function (resolve, reject) {
            if (typeof window.Chart !== "undefined") {
                _chartJsLoaded = true;
                resolve();
                return;
            }
            var s = document.createElement("script");
            // Chart.js 4.4.0 (latest stable as of batch 4)
            s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js";
            s.async = true;
            s.onload = function () {
                _chartJsLoaded = true;
                resolve();
            };
            s.onerror = function () {
                _chartJsLoading = null;
                reject(new Error("Chart.js CDN unreachable"));
            };
            document.head.appendChild(s);
        });
        return _chartJsLoading;
    }

    function destroyAllCharts() {
        for (var id in _chartInstances) {
            if (_chartInstances.hasOwnProperty(id)) {
                try { _chartInstances[id].destroy(); } catch (e) { /* ignore */ }
            }
        }
        _chartInstances = {};
    }

    function destroyChart(id) {
        if (_chartInstances[id]) {
            try { _chartInstances[id].destroy(); } catch (e) { /* ignore */ }
            delete _chartInstances[id];
        }
    }

    // Brand palette (must match static/src/css/crm_dashboard_variables.css)
    var PALETTE = {
        navyDark: "#0B1F3A",
        navyDeep: "#13294B",
        ivory: "#F8F4EA",
        white: "#FFFFFF",
        goldLight: "#D8C08C",
        goldBronze: "#A37C27",
        success: "#198754",
        warning: "#FFC107",
        danger: "#DC3545",
    };
    var SERIES_COLORS = [
        PALETTE.goldBronze, PALETTE.navyDeep, PALETTE.goldLight,
        PALETTE.success, PALETTE.warning, PALETTE.danger, PALETTE.navyDark,
    ];

    function makeChart(canvasId, type, chartData, extraOptions) {
        if (!chartData || !chartData.labels || chartData.labels.length === 0) return null;
        var canvas = document.getElementById(canvasId);
        if (!canvas) return null;
        var ctx = canvas.getContext("2d");
        if (!ctx) return null;

        // Colorize datasets
        var datasets = (chartData.datasets || []).map(function (ds, idx) {
            var c = SERIES_COLORS[idx % SERIES_COLORS.length];
            return Object.assign({}, ds, {
                backgroundColor: ds.backgroundColor || (c + "33"),
                borderColor: ds.borderColor || c,
                borderWidth: ds.borderWidth != null ? ds.borderWidth : 2,
                tension: ds.tension != null ? ds.tension : 0.3,
                fill: type === "line" ? (idx === 0) : false,
            });
        });

        var opts = {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            plugins: {
                legend: {
                    position: "top",
                    labels: { boxWidth: 10, font: { size: 11 } },
                },
                tooltip: { enabled: true },
            },
        };
        if (type === "line" || type === "bar") {
            opts.scales = {
                x: { grid: { display: false }, ticks: { font: { size: 10 } } },
                y: { beginAtZero: true, ticks: { font: { size: 10 } } },
            };
        }
        if (extraOptions) {
            for (var k in extraOptions) {
                if (extraOptions.hasOwnProperty(k)) opts[k] = extraOptions[k];
            }
        }

        // Destroy any existing instance on this canvas
        destroyChart(canvasId);

        try {
            // eslint-disable-next-line no-undef
            var chart = new Chart(ctx, {
                type: type,
                data: { labels: chartData.labels, datasets: datasets },
                options: opts,
            });
            _chartInstances[canvasId] = chart;
            return chart;
        } catch (e) {
            console.error("CED: chart construction failed for " + canvasId, e);
            return null;
        }
    }

    function renderChartsSection(charts) {
        if (!charts) charts = {};
        var sections = [
            { id: "chart-aging", title: "Pipeline Aging — Stale Opportunities", type: "bar", data: charts.pipeline_aging },
            { id: "chart-opp-trend", title: "Opportunity Trend", type: "line", data: charts.opportunity_trend },
            { id: "chart-opp-daily", title: "Opportunities Created (Daily)", type: "line", data: charts.opportunity_trend_daily },
            { id: "chart-opp-weekly", title: "Opportunities Created (Weekly)", type: "bar", data: charts.opportunity_trend_weekly },
            { id: "chart-opp-monthly", title: "Opportunities Created (Monthly)", type: "bar", data: charts.opportunity_trend_monthly },
            { id: "chart-revenue", title: "Revenue Trend", type: "line", data: charts.revenue_trend },
            { id: "chart-conv", title: "Conversion Trend", type: "line", data: charts.conversion_trend },
            { id: "chart-disposition", title: "Opportunities Worked Trend", type: "bar", data: charts.disposition_trend },
            { id: "chart-owner", title: "Pipeline by Owner", type: "bar", data: charts.owner_pipeline },
            { id: "chart-team", title: "Team Performance", type: "bar", data: charts.team_performance },
            { id: "chart-forecast", title: "Revenue Forecast", type: "bar", data: charts.revenue_forecast },
        ];

        var html = sections.map(function (s) {
            var hasData = s.data && s.data.labels && s.data.labels.length > 0;
            return (
                '<div class="ced-chart">' +
                '<div class="ced-chart__header">' +
                '<h3 class="ced-chart__title">' + escapeHtml(s.title) + '</h3>' +
                '</div>' +
                '<div class="ced-chart__body">' +
                (hasData
                    ? '<canvas id="' + s.id + '" class="ced-canvas" height="220"></canvas>'
                    : '<div class="ced-chart__empty">No data for the current filter</div>') +
                '</div>' +
                '</div>'
            );
        }).join("");

        return (
            '<section class="ced-section">' +
            '<h2 class="ced-section__title">Trends &amp; Analytics</h2>' +
            '<div class="ced-charts-grid">' + html + '</div>' +
            '</section>'
        );
    }

    function chartClickOptions(onLabelClick) {
        return {
            onClick: function (evt, elements, chart) {
                if (!elements || !elements.length) return;
                var idx = elements[0].index;
                var label = chart.data.labels[idx];
                onLabelClick(label, idx);
            },
        };
    }

    function mountCharts(charts, payload, filter) {
        if (!window.Chart) {
            // Chart.js not loaded — just show the section without canvases
            return;
        }
        payload = payload || {};
        // Name -> id lookups so bar-chart segments can drill exactly
        // like their table-row counterparts.
        var ownerByName = {};
        ((payload.owner_analytics || {}).owners || []).forEach(function (o) {
            ownerByName[o.name] = o.user_id;
        });

        var defs = [
            { id: "chart-aging", type: "bar", data: charts.pipeline_aging },
            { id: "chart-opp-trend", type: "line", data: charts.opportunity_trend },
            { id: "chart-opp-daily", type: "line", data: charts.opportunity_trend_daily },
            { id: "chart-opp-weekly", type: "bar", data: charts.opportunity_trend_weekly },
            { id: "chart-opp-monthly", type: "bar", data: charts.opportunity_trend_monthly },
            { id: "chart-revenue", type: "line", data: charts.revenue_trend },
            { id: "chart-conv", type: "line", data: charts.conversion_trend },
            { id: "chart-disposition", type: "bar", data: charts.disposition_trend },
            {
                id: "chart-owner", type: "bar", data: charts.owner_pipeline,
                extraOptions: chartClickOptions(function (label) {
                    openDrilldown("owner", ownerByName[label], filter);
                }),
            },
            { id: "chart-team", type: "bar", data: charts.team_performance },
            { id: "chart-forecast", type: "bar", data: charts.revenue_forecast },
        ];
        defs.forEach(function (d) { makeChart(d.id, d.type, d.data, d.extraOptions); });
    }

    // ------------------------------------------------------------------
    // Main render
    // ------------------------------------------------------------------

    function renderPayload(rootEl, filter, payload) {
        var html =
            renderHeader(rootEl, filter, payload) +
            renderKpiOverview(payload.kpi || {}) +
            renderAlerts(payload.alerts || []) +
            renderStartup(payload.startup) +
            renderDisposition(payload.disposition) +
            renderProductivity(payload.productivity) +
            renderOwnerBreakdown(payload.owner_analytics) +
            renderCampaignAnalytics(payload.campaign_analytics) +
            renderFunnel(payload.funnel) +
            renderChartsSection(payload.charts) +
            renderExportBar() +
            '</div>';  // close .ced-dashboard
        rootEl.innerHTML = html;
        // Wire export buttons
        wireExportButtons(filter);
        // Wire click-through drill-down on cards/rows/chart segments
        wireDrilldowns(rootEl, filter);
        // Load and mount charts (lazy CDN load)
        loadChartJs().then(function () {
            mountCharts(payload.charts || {}, payload, filter);
        }).catch(function (e) {
            console.warn("CED: charts not loaded, showing data only", e);
        });
    }

    function renderExportBar() {
        return (
            '<section class="ced-section ced-section--actions">' +
            '<h2 class="ced-section__title">Export &amp; Share</h2>' +
            '<div class="ced-export-bar">' +
            '<button class="ced-btn ced-btn--export" data-export="pdf" title="Download as PDF">' +
            '<i class="fa fa-file-pdf"></i> PDF</button>' +
            '<button class="ced-btn ced-btn--export" data-export="xlsx" title="Download as Excel">' +
            '<i class="fa fa-file-excel"></i> Excel</button>' +
            '<button class="ced-btn ced-btn--export" data-export="csv" title="Download as CSV">' +
            '<i class="fa fa-file-csv"></i> CSV</button>' +
            '<span class="ced-export-status" id="ced-export-status"></span>' +
            '</div>' +
            '</section>'
        );
    }

    function wireExportButtons(filter) {
        var status = document.getElementById("ced-export-status");
        var btns = document.querySelectorAll("[data-export]");
        btns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                var fmt = btn.getAttribute("data-export");
                if (status) status.textContent = "Generating " + fmt.toUpperCase() + "…";
                btn.disabled = true;
                fetch("/crm-dashboard/export", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRF-Token": getCsrfToken(),
                    },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        method: "call",
                        params: { filter: filter, format: fmt },
                        id: Math.floor(Math.random() * 1000000),
                    }),
                }).then(function (resp) {
                    if (!resp.ok) throw new Error("HTTP " + resp.status);
                    return resp.json();
                }).then(function (data) {
                    if (data && data.error) throw new Error(data.error.message || "Export failed");
                    var r = data && data.result;
                    if (r && r.ok === false) throw new Error(r.error || "Export failed");
                    if (r && r.download_url) {
                        // Trigger a browser download
                        var a = document.createElement("a");
                        a.href = r.download_url;
                        a.download = r.filename || ("dashboard." + fmt);
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        if (status) status.textContent = "Downloaded " + (r.filename || "");
                    } else {
                        if (status) status.textContent = "No file returned";
                    }
                }).catch(function (err) {
                    console.error("CED: export failed", err);
                    if (status) status.textContent = "Export failed: " + err.message;
                }).finally(function () {
                    btn.disabled = false;
                });
            });
        });
    }

    function renderLoading(rootEl, filter) {
        rootEl.innerHTML =
            '<div class="ced-dashboard">' +
            '<header class="ced-dashboard__header">' +
            '<h1 class="ced-dashboard__title">' +
            '<i class="fa fa-tachometer-alt"></i> CRM Executive Dashboard' +
            '</h1>' +
            '<div class="ced-dashboard__filter">' +
            '<span class="ced-filter__label">Period:</span>' +
            '<select id="ced-period" class="ced-filter__select">' +
            renderPeriodOptions(filter.period) +
            '</select>' +
            '</div>' +
            '</header>' +
            '<div class="ced-loading-state">' +
            '<i class="fa fa-spinner fa-spin fa-3x"></i>' +
            '<p>Loading dashboard data…</p>' +
            '</div>' +
            '</div>';
    }

    // ------------------------------------------------------------------
    // Data fetch
    // ------------------------------------------------------------------

    function readFilter(rootEl) {
        var ds = rootEl.dataset || {};
        var filter = { period: ds.filterPeriod || "last_30_days" };
        ["filterUser", "filterTeam", "filterSource", "filterStage", "filterCompany"].forEach(function (attr) {
            var key = attr.replace("filter", "").toLowerCase();
            var v = parseInt(ds[attr] || "0", 10);
            if (v) filter[key] = v;
        });
        return filter;
    }

    function fetchData(filter) {
        // Use the standard Odoo JSON-RPC mechanism. We POST to
        // /web/dataset/call_kw with the dashboard data method,
        // OR we can use a direct POST to our /crm-dashboard/data
        // route. The route is the cleaner option.
        return fetch("/crm-dashboard/data", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": getCsrfToken(),
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: { filter: filter },
                id: Math.floor(Math.random() * 1000000),
            }),
        }).then(function (resp) {
            if (!resp.ok) {
                throw new Error("HTTP " + resp.status);
            }
            return resp.json();
        }).then(function (data) {
            if (data && data.error) {
                throw new Error(data.error.data && data.error.data.message
                    ? data.error.data.message
                    : (data.error.message || "Server error"));
            }
            // JSON-RPC response has either {result: ...} or {error: ...}
            if (data && data.result) {
                if (data.result.ok === false) {
                    throw new Error(data.result.error || "Data error");
                }
                return data.result.payload || data.result;
            }
            if (data && data.ok === false) {
                throw new Error(data.error || "Data error");
            }
            return data && data.payload ? data.payload : data;
        });
    }

    // ------------------------------------------------------------------
    // Bootstrap
    // ------------------------------------------------------------------

    // ------------------------------------------------------------------
    // Saved filter helpers
    // ------------------------------------------------------------------

    function jsonRpc(url, params) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRF-Token": getCsrfToken(),
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
                id: Math.floor(Math.random() * 1000000),
            }),
        }).then(function (resp) {
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            return resp.json();
        }).then(function (data) {
            if (data && data.error) {
                throw new Error(data.error.data && data.error.data.message
                    ? data.error.data.message
                    : (data.error.message || "Server error"));
            }
            if (data && data.result) {
                if (data.result.ok === false) {
                    throw new Error(data.result.error || "Server error");
                }
                return data.result.payload;
            }
            return data;
        });
    }

    function loadSavedFiltersList(sel) {
        if (!sel) return;
        return jsonRpc("/crm-dashboard/filters", { op: "list" })
            .then(function (list) {
                if (!Array.isArray(list)) return;
                // Keep the placeholder
                sel.innerHTML = '<option value="">— Choose a saved filter —</option>';
                list.forEach(function (f) {
                    var opt = document.createElement("option");
                    opt.value = JSON.stringify(f.filter);
                    opt.textContent = f.name + (f.is_default ? " (default)" : "");
                    opt.dataset.filterId = f.id;
                    sel.appendChild(opt);
                });
            })
            .catch(function (err) {
                console.warn("CED: could not load saved filters", err);
            });
    }

    function bindControls(rootEl, currentFilter) {
        var periodSel = document.getElementById("ced-period");
        var refreshBtn = document.getElementById("ced-refresh");
        var reloadBtn = document.getElementById("ced-reload");
        var savedSel = document.getElementById("ced-saved-filter");
        var saveBtn = document.getElementById("ced-save-filter");
        if (periodSel) {
            periodSel.addEventListener("change", function () {
                currentFilter.period = periodSel.value;
                loadAndRender(rootEl, currentFilter);
            });
        }
        if (refreshBtn) {
            refreshBtn.addEventListener("click", function () {
                loadAndRender(rootEl, currentFilter);
            });
        }
        if (reloadBtn) {
            reloadBtn.addEventListener("click", function () {
                window.location.reload();
            });
        }
        if (savedSel) {
            // Populate list (idempotent)
            loadSavedFiltersList(savedSel);
            savedSel.addEventListener("change", function () {
                var v = savedSel.value;
                if (!v) return;
                try {
                    var f = JSON.parse(v);
                    Object.keys(f).forEach(function (k) {
                        currentFilter[k] = f[k];
                    });
                    // Reflect the period change in the UI
                    if (periodSel && currentFilter.period) {
                        periodSel.value = currentFilter.period;
                    }
                    loadAndRender(rootEl, currentFilter);
                } catch (e) {
                    console.error("CED: bad saved filter JSON", e);
                }
            });
        }
        if (saveBtn) {
            saveBtn.addEventListener("click", function () {
                var name = window.prompt("Name for this saved filter:",
                    "Filter " + (currentFilter.period || ""));
                if (!name) return;
                var makeDefault = window.confirm(
                    "Make this the default filter that loads on dashboard open?"
                );
                jsonRpc("/crm-dashboard/filters", {
                    op: "create",
                    name: name,
                    filter: currentFilter,
                    is_default: makeDefault,
                }).then(function (rec) {
                    if (rec && rec.name) {
                        loadSavedFiltersList(savedSel);
                        if (window.Odoo && Odoo.__DEBUG__) {
                            console.log("CED: saved filter", rec);
                        }
                        alert("Filter saved: " + rec.name);
                    }
                }).catch(function (err) {
                    alert("Could not save filter: " + err.message);
                });
            });
        }
    }

    function loadAndRender(rootEl, filter) {
        destroyAllCharts();
        renderLoading(rootEl, filter);
        bindControls(rootEl, filter);
        fetchData(filter).then(function (payload) {
            renderPayload(rootEl, filter, payload);
            bindControls(rootEl, filter);
        }).catch(function (err) {
            console.error("CED: data fetch failed", err);
            // Show header + error banner
            var html =
                renderHeader(rootEl, filter, null) +
                renderError(err.message || String(err)) +
                '</div>';
            rootEl.innerHTML = html;
            bindControls(rootEl, filter);
        });
    }

    function init() {
        var rootEl = document.getElementById("ced-root");
        if (!rootEl) return;
        var filter = readFilter(rootEl);
        loadAndRender(rootEl, filter);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
