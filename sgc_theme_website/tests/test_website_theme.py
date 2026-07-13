# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
# =============================================================================
# Stage 3 tests — sgc_theme_website ("Aurum Website Theme").
#
# Pure theme module (spec §5): no new business models. Coverage here maps to:
#   - spec §5 feature 1  -> palette/typography propagation into
#                            web.assets_frontend + web._assets_primary_variables
#                            (TestSgcThemeWebsiteAssets)
#   - spec §5/§6 feature 2 -> the 20 s_sgc_* snippets (original 7 + 13 "SGC
#                            TECH" v2 snippets) registered in the Website
#                            Builder block menu under the "SGC TECH" group,
#                            thumbnails resolving
#                            (TestSgcThemeWebsiteSnippetsRegistry)
#   - spec §5 feature 4  -> branded header/footer template rendered on the
#                            demo page (TestSgcThemeWebsiteDemoPage)
#   - spec §5 feature 5  -> the assembled demo/showcase page renders
#                            (TestSgcThemeWebsiteDemoPage)
#   - spec §5 feature 6 / §8 -> animation layer honours
#                            prefers-reduced-motion, both in compiled CSS and
#                            in the JS interaction logic itself
#                            (TestSgcThemeWebsiteAssets +
#                            TestSgcThemeWebsiteReducedMotionJs)
#   - spec §2.3 builder options -> the OWL BuilderOption plugin bundle
#                            compiles (TestSgcThemeWebsiteAssets)
#   - drag/drop -> browser tour (TestSgcThemeWebsiteTours); SKIPS (not
#                            fails) in Chrome-less environments, see the tour
#                            file's docstring.
# =============================================================================

import os

from lxml import html as lxml_html

from odoo.addons.http_routing.tests.common import MockRequest
from odoo.modules.module import get_module_path
from odoo.tests import HttpCase, TransactionCase, tagged

NAVY = "#0F2C4C"
GOLD = "#C9A227"
CREAM = "#F5EFE0"

SGC_SNIPPET_KEYS = [
    "s_sgc_hero",
    "s_sgc_feature_hex",
    "s_sgc_stats",
    "s_sgc_testimonial",
    "s_sgc_cta",
    "s_sgc_showcase",
    "s_sgc_footer",
    # v2: 13 additional "SGC TECH" snippets
    "s_sgc_brand_hero",
    "s_sgc_split_feature",
    "s_sgc_before_after",
    "s_sgc_three_pillars",
    "s_sgc_comparison_table",
    "s_sgc_dashboard_showcase",
    "s_sgc_layer_pyramid",
    "s_sgc_flow_diagram",
    "s_sgc_roadmap",
    "s_sgc_hexagon_grid",
    "s_sgc_leadership",
    "s_sgc_pricing_tiers",
    "s_sgc_contact_cta",
]

# The assembled demo page (views/pages/demo.xml) only renders the original 7
# snippets -- it was not extended when the 13 v2 "SGC TECH" snippets were
# added (out of scope for that build; demo.xml is untouched). Keep this list
# separate from SGC_SNIPPET_KEYS (used by the block-menu registry / thumbnail
# tests) so that distinction stays correct instead of coupling the two.
SGC_DEMO_SNIPPET_KEYS = SGC_SNIPPET_KEYS[:7]


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteInstall(TransactionCase):

    def test_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_website")])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, "installed")

    def test_depends_on_shared_token_layer(self):
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_website")])
        dep_names = module.dependencies_id.mapped("name")
        self.assertIn("sgc_theme_common", dep_names)
        self.assertIn("website", dep_names)


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteAssets(TransactionCase):
    """Compiles the real asset bundles this theme contributes to."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.frontend_css = cls._compiled("web.assets_frontend", css=True, js=False)
        cls.frontend_js = cls._compiled("web.assets_frontend", css=False, js=True)
        cls.builder_js = cls._compiled("website.website_builder_assets", css=False, js=True)

    @classmethod
    def _compiled(cls, bundle_name, css, js):
        bundle = cls.env["ir.qweb"]._get_asset_bundle(bundle_name, css=css, js=js)
        attachments = bundle.css() if css else bundle.js()
        # bundle.css()/js() may return more than one ir.attachment (e.g. a
        # sourcemap companion); concatenate so substring asserts see it all.
        return b"\n".join(raw or b"" for raw in attachments.mapped("raw")).decode()

    def test_frontend_bundle_compiles(self):
        self.assertTrue(self.frontend_css)

    def test_frontend_bundle_recoloured_with_sgc_palette(self):
        css_lower = self.frontend_css.lower()
        self.assertIn(NAVY.lower(), css_lower, "feature 1: SGC navy missing from web.assets_frontend")
        self.assertIn(GOLD.lower(), css_lower, "feature 1: SGC gold missing from web.assets_frontend")
        self.assertIn(CREAM.lower(), css_lower, "feature 1: SGC cream missing from web.assets_frontend")

    def test_frontend_bundle_uses_sgc_serif_headings(self):
        self.assertIn("Playfair Display", self.frontend_css)

    def test_frontend_bundle_theme_color_palette_mapped(self):
        """primary_variables.scss's $o-user-theme-color-palette override
        should reach Odoo's compiled --o-color-* custom properties."""
        self.assertIn("--o-color-1", self.frontend_css)

    def test_frontend_bundle_has_gold_hexagon_motif(self):
        self.assertIn(".sgc-hex", self.frontend_css)

    def test_frontend_bundle_does_not_contain_backend_only_selectors(self):
        """NOTE: bare classes like `.o_web_client`/`.o_main_navbar` are
        unsuitable here — core Odoo legitimately reuses them in some
        frontend-embedded widgets. These compound selectors are unique to
        sgc_theme_backend's backend_theme.scss."""
        for backend_only_selector in (
            ".o_form_view .o_form_sheet",
            ".o_statusbar_status .o_arrow_button",
            ".o_list_view thead th",
            ".o_searchview_facet",
        ):
            self.assertNotIn(backend_only_selector, self.frontend_css)

    def test_frontend_bundle_gates_motion_on_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.frontend_css)

    def test_frontend_interactions_registered_in_bundle(self):
        """feature 6 / spec §8 tiers b (scroll-reveal, KPI count-up) and c
        (3D tilt) are actually shipped in the compiled bundle."""
        for interaction_class in ("SgcScrollReveal", "SgcStatCounter", "SgcTilt"):
            self.assertIn(interaction_class, self.frontend_js)

    def test_builder_option_plugin_bundle_compiles(self):
        """spec §2.3 / §12: the v19 OWL html_builder BuilderOption plugin for
        all 7 snippets compiles without a JS syntax/parse error."""
        self.assertTrue(self.builder_js)
        for option_class in (
            "SgcHeroOption", "SgcFeatureHexOption", "SgcStatsOption",
            "SgcTestimonialOption", "SgcCtaOption", "SgcShowcaseOption",
            "SgcFooterOption",
        ):
            self.assertIn(option_class, self.builder_js)
        self.assertIn("sgcSnippetsOption", self.builder_js)


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteSnippetsRegistry(HttpCase):
    """feature 2 / spec §6: all 7 SGC snippets are registered into the
    Website Builder block menu, with thumbnails that resolve."""

    def _render_snippets_panel(self):
        website = self.env["website"].browse(1)
        with MockRequest(self.env, website=website):
            return self.env["ir.ui.view"].render_public_asset("website.snippets")

    def test_all_seven_snippets_registered_in_block_menu(self):
        tree = lxml_html.fromstring(self._render_snippets_panel())
        els = tree.xpath("//*[@data-oe-snippet-key]")
        sgc_keys = sorted({
            el.attrib["data-oe-snippet-key"] for el in els
            if el.attrib["data-oe-snippet-key"].startswith("s_sgc_")
        })
        self.assertEqual(sgc_keys, sorted(SGC_SNIPPET_KEYS))

    def test_sgc_group_tile_registered(self):
        """The <t snippet-group="sgc" ... string="SGC TECH"> entry compiles
        into a <div name="SGC TECH" data-o-snippet-group="sgc" ...> tile
        inside #snippet_groups (verified against the live-rendered panel).
        Renamed from "SGC" -> "SGC TECH" alongside the v2 13-snippet add."""
        tree = lxml_html.fromstring(self._render_snippets_panel())
        groups = tree.xpath("//*[@data-o-snippet-group='sgc']")
        self.assertTrue(groups, "the 'SGC TECH' snippet-group tile should be registered in #snippet_groups")
        self.assertEqual(groups[0].attrib.get("name"), "SGC TECH")

    def test_snippet_thumbnails_resolve(self):
        thumbnail_urls = [
            "/sgc_theme_website/static/src/img/snippets_thumbs/s_sgc_group.svg",
        ] + [
            f"/sgc_theme_website/static/src/img/snippets_thumbs/{key}.svg"
            for key in SGC_SNIPPET_KEYS
        ]
        for thumbnail_url in thumbnail_urls:
            response = self.url_open(thumbnail_url)
            self.assertEqual(
                response.status_code, 200,
                f"snippet thumbnail should resolve: {thumbnail_url}",
            )


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteDemoPage(HttpCase):
    """feature 5: the assembled demo/showcase page (professional services +
    SaaS vertical, spec §10 Q3) renders and includes all 7 snippets."""

    def test_demo_page_record_exists_and_is_published(self):
        page = self.env.ref("sgc_theme_website.sgc_demo_page")
        self.assertTrue(page.is_published)
        self.assertEqual(page.url, "/aurum-demo")

    def test_demo_page_renders_all_seven_snippets(self):
        response = self.url_open("/aurum-demo")
        self.assertEqual(response.status_code, 200)
        content = response.text
        for section_class in SGC_DEMO_SNIPPET_KEYS:
            self.assertIn(section_class, content, f"demo page should render section {section_class!r}")

    def test_demo_page_includes_branded_footer_link(self):
        """feature 4: branded footer with the compliant sgctech.ai link."""
        response = self.url_open("/aurum-demo")
        self.assertIn("sgctech.ai", response.text)


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteReducedMotionJs(TransactionCase):
    """spec §6/§8: unit-level (non-browser) check that every animation
    interaction actually gates itself on prefers-reduced-motion."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scroll_reveal_js = cls._read("sgc_scroll_reveal.js")
        cls.stat_counter_js = cls._read("sgc_stat_counter.js")
        cls.tilt_js = cls._read("sgc_tilt.js")

    @classmethod
    def _read(cls, filename):
        module_path = get_module_path("sgc_theme_website")
        path = os.path.join(module_path, "static", "src", "js", filename)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_scroll_reveal_checks_prefers_reduced_motion(self):
        self.assertIn("prefers-reduced-motion: reduce", self.scroll_reveal_js)
        self.assertIn("this.reduced", self.scroll_reveal_js)

    def test_scroll_reveal_skips_observer_when_reduced(self):
        self.assertIn("if (this.reduced", self.scroll_reveal_js)

    def test_stat_counter_checks_prefers_reduced_motion(self):
        self.assertIn("prefers-reduced-motion: reduce", self.stat_counter_js)
        self.assertIn("this.reduced", self.stat_counter_js)

    def test_stat_counter_shows_final_value_immediately_when_reduced(self):
        self.assertIn("this.render(this.reduced ? this.target : 0)", self.stat_counter_js)

    def test_tilt_checks_prefers_reduced_motion(self):
        self.assertIn("prefers-reduced-motion: reduce", self.tilt_js)
        self.assertIn("if (this.reduced", self.tilt_js)

    def test_tilt_also_disables_on_touch_pointers(self):
        self.assertIn('ev.pointerType === "touch"', self.tilt_js)


@tagged("post_install", "-at_install")
class TestSgcThemeWebsiteTours(HttpCase):
    """Browser tour: drags every SGC snippet onto a page, opens its builder
    options panel, removes it, then does a full insert -> save -> reload
    round trip on the Hero snippet.

    Requires a headless-Chrome-capable test runner. Odoo's own test
    framework SKIPS (unittest.SkipTest), rather than fails, when Chrome is
    not available (odoo/tests/common.py::_find_executable) — that is
    expected and correct behaviour in a Chrome-less CI/dev environment.
    """

    def test_insert_all_sgc_snippets_tour(self):
        self.start_tour("/", "sgc_snippets_insert_all", login="admin", timeout=300)
