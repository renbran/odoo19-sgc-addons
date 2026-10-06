# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
{
    "name": "Aurum Website Theme",
    "summary": "Premium SGC Website Builder theme with drag-drop snippets",
    "description": """
Aurum Website Theme
===================

A drag-and-drop Website Builder theme in the SGC navy / gold / cream visual
language — elegant serif headings, the signature gold-hexagon motif, and a
library of twenty inline-editable snippets, grouped under the "SGC TECH"
block category, that a non-developer can assemble into premium marketing
pages.

Snippet library (v1 — original seven)
--------------------------------------
* SGC Hero — logo, serif tagline and CTA
* Gold-Hexagon Feature Grid — the signature badge motif
* Animated KPI / Stat Counters — count-up on scroll
* Testimonial Block — quote, avatar, name & role
* CTA Band — full-width navy/gold call-to-action
* Image / Mockup Showcase — with an optional 3D tilt
* SGC Footer — brand footer, tagline and contact

Snippet library (v2 — thirteen additional "SGC TECH" sections)
-----------------------------------------------------------------
* Brand Hero, Split Feature, Before / After, Three Pillars,
  Comparison Table, Dashboard Showcase, Layer Pyramid, Flow Diagram,
  Roadmap, Hexagon Grid, Leadership, Pricing Tiers, Contact CTA.
  Each ships a shared decorative-layer option panel: a landmark watermark
  (Burj Khalifa / Burj Al Arab / Sheikh Zayed Mosque / Dubai skyline / none),
  a geometry overlay (hexagon lattice / circuit / arabesque corner /
  hairline frame / none), a palette variant (Navy-on-Cream / Cream-on-Navy /
  Gold-Accent) and an SGC logo lockup toggle.

Motion & accessibility
----------------------
Tasteful CSS micro-interactions, IntersectionObserver scroll-reveal and a
subtle 3D tilt on showcase cards — all disabled under
``prefers-reduced-motion``. No Lottie, no WebGL: fast by default. All
decorative watermark/geometry layers are static (no animation) and opacity-
capped to protect WCAG AA text contrast.

Changelog
---------
19.0.2.0.0 — added 13 new "SGC TECH" snippets (see above) plus the shared
watermark/geometry/palette/logo decorative layer (new
addons/sgc_theme_common static SVG assets + _sgc_decor.scss); renamed the
block-menu group from "SGC" to "SGC TECH".
19.0.1.0.0 — initial release, seven SGC snippets.

Part of the Aurum theme family (shares the Aurum Design Tokens layer).
""",
    "author": "SGC TECH",
    "maintainer": "SGC TECH",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    "category": "Theme/Corporate",
    "version": "19.0.2.0.0",
    "license": "LGPL-3",
    "depends": ["website", "sgc_theme_common"],
    "data": [
        # Snippet templates (must load before they are registered/used)
        "views/snippets/s_sgc_hero.xml",
        "views/snippets/s_sgc_feature_hex.xml",
        "views/snippets/s_sgc_stats.xml",
        "views/snippets/s_sgc_testimonial.xml",
        "views/snippets/s_sgc_cta.xml",
        "views/snippets/s_sgc_showcase.xml",
        "views/snippets/s_sgc_footer.xml",
        # v2: 13 additional "SGC TECH" snippets
        "views/snippets/s_sgc_brand_hero.xml",
        "views/snippets/s_sgc_split_feature.xml",
        "views/snippets/s_sgc_before_after.xml",
        "views/snippets/s_sgc_three_pillars.xml",
        "views/snippets/s_sgc_comparison_table.xml",
        "views/snippets/s_sgc_dashboard_showcase.xml",
        "views/snippets/s_sgc_layer_pyramid.xml",
        "views/snippets/s_sgc_flow_diagram.xml",
        "views/snippets/s_sgc_roadmap.xml",
        "views/snippets/s_sgc_hexagon_grid.xml",
        "views/snippets/s_sgc_leadership.xml",
        "views/snippets/s_sgc_pricing_tiers.xml",
        "views/snippets/s_sgc_contact_cta.xml",
        # Register the snippets into the Website Builder block menu
        "views/snippets/snippets.xml",
        # Assembled demo / showcase page (also the store screenshot)
        "views/pages/demo.xml",
    ],
    "assets": {
        # Site-wide palette + fonts (mapped from the shared SGC tokens)
        "web._assets_primary_variables": [
            "sgc_theme_website/static/src/scss/primary_variables.scss",
        ],
        # Bootstrap 5 variable overrides (radius, fonts) BEFORE BS compiles
        "web._assets_frontend_helpers": [
            "sgc_theme_website/static/src/scss/bootstrap_overridden.scss",
        ],
        # Rendered theme + snippet styles and animations (frontend ONLY)
        "web.assets_frontend": [
            "sgc_theme_website/static/src/scss/theme.scss",
            "sgc_theme_website/static/src/scss/_sgc_decor.scss",
            "sgc_theme_website/static/src/scss/snippets.scss",
            "sgc_theme_website/static/src/scss/snippets_v2.scss",
            "sgc_theme_website/static/src/js/sgc_scroll_reveal.js",
            "sgc_theme_website/static/src/js/sgc_stat_counter.js",
            "sgc_theme_website/static/src/js/sgc_tilt.js",
        ],
        # Editor-side: OWL builder option plugins + their XML templates.
        # This bundle already includes html_builder.assets.
        "website.website_builder_assets": [
            "sgc_theme_website/static/src/builder/sgc_snippets_option_plugin.js",
            "sgc_theme_website/static/src/builder/sgc_snippets_options.xml",
        ],
        # Browser tour(s) for Stage 3 test coverage (Odoo's standard
        # web_tour.tours registry bundle — mirrors website/static/tests/tours).
        "web.assets_tests": [
            "sgc_theme_website/static/tests/tours/sgc_snippets_insert.js",
        ],
    },
    # First image ending in _screenshot is the big store preview (spec §2.4).
    "images": [
        "static/description/sgc_website_screenshot.png",
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
