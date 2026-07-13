/** @odoo-module **/

import { Component, useState, onWillStart, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AuroraMap extends Component {
    static template = "AuroraMap";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            projects: [],
            clusters: [],
            zoom: 1,
            hoveredProject: null,
            selectedProject: null,
            heatmapEnabled: true,
        });

        onWillStart(async () => {
            await this.loadProjects();
        });
    }

    async loadProjects() {
        // Odoo 19's Domain validator rejects `0` as a top-level item, and the
        // OWL ORM serializes `(field, '!=', 0)` poorly across the JSON-RPC
        // boundary. Fetch all projects and filter out the unset coordinates
        // client-side instead.
        const allProjects = await this.orm.searchRead("construction.project",
            [],
            ["name", "latitude", "longitude", "rag_status", "progress", "budget_consumed", "emirate",
             "project_manager_id", "contract_value", "margin_percent", "end_date", "weather_status",
             "last_site_diary", "open_ncr_count"]
        );
        this.state.projects = (allProjects || []).filter(
            (p) => Boolean(p.latitude) && Boolean(p.longitude)
        );
        this.computeClusters();
    }

    computeClusters() {
        // Simple distance-based clustering
        const clusters = [];
        const clusterRadius = 0.5; // Roughly degrees for this simplified implementation

        const processed = new Set();

        for (const p of this.state.projects) {
            if (processed.has(p.id)) continue;

            const cluster = {
                id: `cluster_${p.id}`,
                center: { lat: p.latitude, lon: p.longitude },
                projects: [p],
                worstStatus: p.rag_status
            };

            processed.add(p.id);

            for (const other of this.state.projects) {
                if (processed.has(other.id)) continue;

                const dist = Math.sqrt(
                    Math.pow(p.latitude - other.latitude, 2) +
                    Math.pow(p.longitude - other.longitude, 2)
                );

                if (dist < clusterRadius) {
                    cluster.projects.push(other);
                    processed.add(other.id);
                    // Update worst status logic (red > orange > amber > green)
                    const statusRank = { red: 3, orange: 2, amber: 1, green: 0 };
                    if (statusRank[other.rag_status] > statusRank[cluster.worstStatus]) {
                        cluster.worstStatus = other.rag_status;
                    }
                }
            }
            clusters.push(cluster);
        }
        this.state.clusters = clusters;
    }

    projectToSVG(lat, lon) {
        // UAE Bounding Box: Lat 22.5 to 26.5, Lon 51.0 to 56.5
        // SVG Map viewbox usually 0 0 1000 800
        const minLat = 22.5;
        const maxLat = 26.5;
        const minLon = 51.0;
        const maxLon = 56.5;

        const x = ((lon - minLon) / (maxLon - minLon)) * 1000;
        const y = 800 - (((lat - minLat) / (maxLat - minLat)) * 800);

        return { x, y };
    }

    onPinClick(project) {
        this.state.selectedProject = project;
    }

    closePopup() {
        this.state.selectedProject = null;
    }

    navigateToProject(projectId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "construction.project",
            res_id: projectId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatCurrency(amount) {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: 'AED',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(amount);
    }
}
