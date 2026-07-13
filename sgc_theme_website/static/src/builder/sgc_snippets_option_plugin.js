/** @odoo-module */
// (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
// =============================================================================
// Aurum Website Theme — Website Builder option plugin (Odoo 19 html_builder).
// -----------------------------------------------------------------------------
// Registers the OWL builder-option panels for the seven SGC snippets. Each
// entry maps a snippet CSS selector to an option template rendered in the
// editor sidebar. The templates use only the built-in builder actions
// (classAction / dataAttributeAction / styleAction), so no custom BuilderAction
// classes are needed for this first pass.
//
// Verified against Odoo 19 source (html_builder + website): plugins extend
// `@html_editor/plugin`, expose `builder_options`, and are registered in the
// "builder-plugins" registry category. Loaded via the
// `website.website_builder_assets` bundle.
// =============================================================================

import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

// Each snippet option is an OWL component extending BaseOptionComponent that
// declares the option template and the CSS selector of the snippet it applies
// to. This is the Odoo 19 html_builder API (verified against the core
// BadgeOption / SeparatorOption plugins). The Builder* components used inside
// the templates (BuilderRow / BuilderSelect / BuilderCheckbox …) are registered
// globally by html_builder, so no `static components` declaration is needed.

class SgcHeroOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcHeroOption";
    static selector = ".s_sgc_hero";
}
class SgcFeatureHexOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcFeatureHexOption";
    static selector = ".s_sgc_feature_hex";
}
class SgcStatsOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcStatsOption";
    static selector = ".s_sgc_stats";
}
class SgcTestimonialOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcTestimonialOption";
    static selector = ".s_sgc_testimonial";
}
class SgcCtaOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcCtaOption";
    static selector = ".s_sgc_cta";
}
class SgcShowcaseOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcShowcaseOption";
    static selector = ".s_sgc_showcase";
}
class SgcFooterOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcFooterOption";
    static selector = ".s_sgc_footer";
}

// -----------------------------------------------------------------------------
// v2: 13 additional "SGC TECH" snippets. Each option panel exposes the same 4
// shared-decor rows (landmark watermark / geometry style / palette variant /
// show SGC logo) driven by the classAction/dataAttributeAction utilities in
// _sgc_decor.scss — see sgc_snippets_options.xml for the row definitions.
// -----------------------------------------------------------------------------
class SgcBrandHeroOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcBrandHeroOption";
    static selector = ".s_sgc_brand_hero";
}
class SgcSplitFeatureOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcSplitFeatureOption";
    static selector = ".s_sgc_split_feature";
}
class SgcBeforeAfterOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcBeforeAfterOption";
    static selector = ".s_sgc_before_after";
}
class SgcThreePillarsOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcThreePillarsOption";
    static selector = ".s_sgc_three_pillars";
}
class SgcComparisonTableOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcComparisonTableOption";
    static selector = ".s_sgc_comparison_table";
}
class SgcDashboardShowcaseOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcDashboardShowcaseOption";
    static selector = ".s_sgc_dashboard_showcase";
}
class SgcLayerPyramidOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcLayerPyramidOption";
    static selector = ".s_sgc_layer_pyramid";
}
class SgcFlowDiagramOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcFlowDiagramOption";
    static selector = ".s_sgc_flow_diagram";
}
class SgcRoadmapOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcRoadmapOption";
    static selector = ".s_sgc_roadmap";
}
class SgcHexagonGridOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcHexagonGridOption";
    static selector = ".s_sgc_hexagon_grid";
}
class SgcLeadershipOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcLeadershipOption";
    static selector = ".s_sgc_leadership";
}
class SgcPricingTiersOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcPricingTiersOption";
    static selector = ".s_sgc_pricing_tiers";
}
class SgcContactCtaOption extends BaseOptionComponent {
    static template = "sgc_theme_website.SgcContactCtaOption";
    static selector = ".s_sgc_contact_cta";
}

class SgcSnippetsOptionPlugin extends Plugin {
    static id = "sgcSnippetsOption";

    resources = {
        builder_options: [
            SgcHeroOption,
            SgcFeatureHexOption,
            SgcStatsOption,
            SgcTestimonialOption,
            SgcCtaOption,
            SgcShowcaseOption,
            SgcFooterOption,
            SgcBrandHeroOption,
            SgcSplitFeatureOption,
            SgcBeforeAfterOption,
            SgcThreePillarsOption,
            SgcComparisonTableOption,
            SgcDashboardShowcaseOption,
            SgcLayerPyramidOption,
            SgcFlowDiagramOption,
            SgcRoadmapOption,
            SgcHexagonGridOption,
            SgcLeadershipOption,
            SgcPricingTiersOption,
            SgcContactCtaOption,
        ],
    };
}

registry
    .category("builder-plugins")
    .add(SgcSnippetsOptionPlugin.id, SgcSnippetsOptionPlugin);
