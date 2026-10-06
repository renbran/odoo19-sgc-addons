/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { GraphRenderer } from "@web/views/graph/graph_renderer";

// Fix 3: Only override colors when dark mode is active.
// Respect Odoo 19's native color scheme handling.
function getThemeFontColor() {
    try {
        const cookies = document.cookie.split(";").reduce((acc, c) => {
            const [k, v] = c.trim().split("=");
            acc[k] = v;
            return acc;
        }, {});
        return cookies["color_scheme"] === "dark" ? "#ffffff" : null;
    } catch {
        return null;
    }
}

patch(GraphRenderer.prototype, {

    getScaleOptions() {
        const options = super.getScaleOptions();
        const fontColor = getThemeFontColor();
        if (!fontColor) {
            return options;
        }

        if (options.x?.ticks) {
            options.x.ticks.color = fontColor;
        }
        if (options.x?.title) {
            options.x.title.color = fontColor;
        }

        if (options.y?.ticks) {
            options.y.ticks.color = fontColor;
        }
        if (options.y?.title) {
            options.y.title.color = fontColor;
        }

        return options;
    },

    getLegendOptions() {
        const options = super.getLegendOptions();
        const fontColor = getThemeFontColor();
        if (!fontColor) {
            return options;
        }

        if (options.labels?.generateLabels) {
            const originalGenerateLabels = options.labels.generateLabels;

            options.labels.generateLabels = (chart) => {
                return originalGenerateLabels(chart).map(label => ({
                    ...label,
                    fontColor: fontColor,
                }));
            };
        }

        return options;
    },

});
