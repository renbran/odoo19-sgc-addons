/** @odoo-module */
// (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
// =============================================================================
// Stage 3 test coverage — browser tour.
// -----------------------------------------------------------------------------
// Drags every one of the twenty SGC snippets (original 7 + 13 "SGC TECH" v2
// snippets) onto a test page, opens each snippet's builder options panel
// (proves the OWL BuilderOption plugin in sgc_snippets_option_plugin.js /
// sgc_snippets_options.xml loads without error), then removes it. Finishes
// with a full insert -> save -> reload round trip on the signature Hero
// snippet.
//
// Uses only the officially exposed `@website/js/tours/tour_utils` helpers
// (insertSnippet / clickOnSave / ...), the same helpers Odoo's own
// `website/static/tests/tours/*.js` use, so this stays valid across minor
// v19 point releases.
//
// NOTE: HttpCase.start_tour() needs a headless-Chrome-capable runner. When
// Chrome is not installed, Odoo's own test framework raises
// unittest.SkipTest (see odoo/tests/common.py::_find_executable), so this
// tour is SKIPPED rather than failed in Chrome-less environments.
// =============================================================================

import {
    clickOnEditAndWaitEditMode,
    insertSnippet,
    goBackToBlocks,
    clickOnSave,
} from "@website/js/tours/tour_utils";
import { registry } from "@web/core/registry";

const SGC_SNIPPETS = [
    { id: "s_sgc_hero", name: "SGC Hero" },
    { id: "s_sgc_feature_hex", name: "SGC Feature Grid" },
    { id: "s_sgc_stats", name: "SGC Stat Counters" },
    { id: "s_sgc_testimonial", name: "SGC Testimonial" },
    { id: "s_sgc_cta", name: "SGC CTA Band" },
    { id: "s_sgc_showcase", name: "SGC Showcase" },
    { id: "s_sgc_footer", name: "SGC Footer" },
    // v2: 13 additional "SGC TECH" snippets
    { id: "s_sgc_brand_hero", name: "SGC Brand Hero" },
    { id: "s_sgc_split_feature", name: "SGC Split Feature" },
    { id: "s_sgc_before_after", name: "SGC Before / After" },
    { id: "s_sgc_three_pillars", name: "SGC Three Pillars" },
    { id: "s_sgc_comparison_table", name: "SGC Comparison Table" },
    { id: "s_sgc_dashboard_showcase", name: "SGC Dashboard Showcase" },
    { id: "s_sgc_layer_pyramid", name: "SGC Layer Pyramid" },
    { id: "s_sgc_flow_diagram", name: "SGC Flow Diagram" },
    { id: "s_sgc_roadmap", name: "SGC Roadmap" },
    { id: "s_sgc_hexagon_grid", name: "SGC Hexagon Grid" },
    { id: "s_sgc_leadership", name: "SGC Leadership" },
    { id: "s_sgc_pricing_tiers", name: "SGC Pricing Tiers" },
    { id: "s_sgc_contact_cta", name: "SGC Contact CTA" },
];

function insertOpenOptionsAndRemove(snippet) {
    return [
        ...insertSnippet({ id: snippet.id, name: snippet.name, groupName: "SGC TECH" }),
        {
            content: `Click on the inserted ${snippet.name} snippet`,
            trigger: `:iframe #wrap [data-snippet="${snippet.id}"]`,
            run: "click",
        },
        {
            content: `Check the ${snippet.name} builder options panel opened (proves the OWL BuilderOption plugin loaded without error)`,
            trigger: ".o_customize_tab",
        },
        {
            content: `Remove the ${snippet.name} snippet`,
            trigger: ".options-container .oe_snippet_remove:last",
            run: "click",
        },
        goBackToBlocks(),
    ];
}

registry.category("web_tour.tours").add("sgc_snippets_insert_all", {
    url: "/",
    steps: () => [
        ...clickOnEditAndWaitEditMode(),
        ...SGC_SNIPPETS.flatMap(insertOpenOptionsAndRemove),
        // Final round trip: insert the signature Hero snippet and persist it.
        ...insertSnippet({ id: "s_sgc_hero", name: "SGC Hero", groupName: "SGC TECH" }),
        {
            content: "Confirm the Hero snippet is on the page before saving",
            trigger: ":iframe #wrap [data-snippet='s_sgc_hero']",
        },
        ...clickOnSave(),
        {
            content: "Confirm the Hero snippet survived the save (and a fresh render)",
            trigger: ":iframe #wrap [data-snippet='s_sgc_hero']",
        },
    ],
});
