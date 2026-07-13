# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
# =============================================================================
# Stage 3 tests — sgc_theme_backend ("Aurum Backend Theme").
#
# Pure asset/QWeb theme module (spec §4): no new python models, no security
# groups. What matters here:
#   1. clean install;
#   2. web.assets_backend compiles without error and is actually recoloured
#      with the SGC palette (feature 1: global palette skin);
#   3. the restyle stays CONFINED to the backend bundle — it must never leak
#      into web.assets_frontend, and web.assets_backend must never contain
#      website-only (s_sgc_*) selectors (spec §2.1 "prevent cross-leaking");
#   4. tier-(a)-only motion is gated on prefers-reduced-motion everywhere
#      (spec §4 hard constraint, §8);
#   5. the QWeb PDF report accent (feature 8) actually renders navy/gold into
#      the standard external report layout;
#   6. a real backend page (the web client shell) loads with the theme
#      installed.
#
# Full WCAG-AA contrast MEASUREMENT is explicitly out of scope here — that is
# Stage 4 (readiness-auditor)'s job. We only sanity-check that the
# accessibility-relevant CSS (tokens, reduced-motion gating) is present.
# =============================================================================

from odoo.tests import HttpCase, TransactionCase, tagged

NAVY = "#0F2C4C"
GOLD = "#C9A227"
CREAM = "#F5EFE0"


@tagged("post_install", "-at_install")
class TestSgcThemeBackendInstall(TransactionCase):

    def test_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_backend")])
        self.assertEqual(len(module), 1)
        self.assertEqual(module.state, "installed")

    def test_depends_on_shared_token_layer(self):
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_backend")])
        dep_names = module.dependencies_id.mapped("name")
        self.assertIn("sgc_theme_common", dep_names)


@tagged("post_install", "-at_install")
class TestSgcThemeBackendAssets(TransactionCase):
    """Compiles the real asset bundles (post_install so the whole registry,
    including sgc_theme_common's shared token layer, is settled)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend_css = cls._compiled_css("web.assets_backend")
        cls.frontend_css = cls._compiled_css("web.assets_frontend")

    @classmethod
    def _compiled_css(cls, bundle_name):
        bundle = cls.env["ir.qweb"]._get_asset_bundle(bundle_name, css=True, js=False)
        attachments = bundle.css()
        # bundle.css() may return more than one ir.attachment (e.g. a css.map
        # sourcemap companion); concatenate so substring asserts see it all.
        return b"\n".join(raw or b"" for raw in attachments.mapped("raw")).decode()

    def test_backend_bundle_compiles(self):
        self.assertTrue(self.backend_css, "web.assets_backend should compile to non-empty CSS")

    def test_backend_bundle_recoloured_with_sgc_palette(self):
        css_lower = self.backend_css.lower()
        self.assertIn(NAVY.lower(), css_lower, "navy chrome (feature 1) missing from web.assets_backend")
        self.assertIn(GOLD.lower(), css_lower, "gold accent missing from web.assets_backend")
        self.assertIn(CREAM.lower(), css_lower, "cream canvas missing from web.assets_backend")

    def test_backend_bundle_headings_use_sgc_serif(self):
        self.assertIn("Playfair Display", self.backend_css)

    def test_backend_key_view_selectors_present(self):
        """Spot-check features 2-7 (form/list/kanban/search/buttons/dialogs)
        are actually present as compiled selectors, not just declared in
        source and silently dropped/renamed by the SCSS compiler."""
        for selector in (
            ".o_main_navbar",
            ".o_form_view",
            ".o_list_view",
            ".o_kanban_view",
            ".o_searchview",
            ".modal-content",
            ".o_notification",
        ):
            self.assertIn(
                selector, self.backend_css,
                f"expected selector {selector!r} in compiled web.assets_backend",
            )

    def test_backend_bundle_gates_motion_on_reduced_motion(self):
        self.assertIn("prefers-reduced-motion", self.backend_css)

    def test_backend_bundle_does_not_leak_website_only_snippet_classes(self):
        """spec §2.1: backend SCSS goes ONLY in web.assets_backend; a file in
        one bundle must not compile into the other. This guards against the
        website theme's s_sgc_* snippet selectors ever ending up here."""
        for website_only_selector in (
            ".s_sgc_hero", ".s_sgc_feature_hex", ".s_sgc_stats",
            ".s_sgc_testimonial", ".s_sgc_cta", ".s_sgc_showcase", ".s_sgc_footer",
        ):
            self.assertNotIn(website_only_selector, self.backend_css)

    def test_frontend_bundle_does_not_contain_backend_only_selectors(self):
        """Confinement check from the other direction: none of OUR backend
        theme's compound web-client selectors should leak into
        web.assets_frontend. NOTE: bare classes like `.o_web_client` or
        `.o_main_navbar` are unsuitable here — core Odoo legitimately reuses
        them in some frontend-embedded widgets, so a bare-class check would
        false-positive on core CSS that has nothing to do with our SCSS.
        These compound selectors are unique to backend_theme.scss."""
        for backend_only_selector in (
            ".o_form_view .o_form_sheet",
            ".o_statusbar_status .o_arrow_button",
            ".o_list_view thead th",
            ".o_searchview_facet",
        ):
            self.assertNotIn(backend_only_selector, self.frontend_css)


@tagged("post_install", "-at_install")
class TestSgcThemeBackendReport(TransactionCase):
    """Feature 8: light, print-safe SGC accent on QWeb PDF business reports."""

    def test_report_accent_template_registered(self):
        view = self.env.ref("sgc_theme_backend.sgc_report_external_layout_standard")
        self.assertEqual(view.inherit_id, self.env.ref("web.external_layout_standard"))
        self.assertTrue(view.active)

    def test_report_accent_renders_navy_gold_into_external_layout(self):
        """Renders the real, standard external report layout (with our
        inherited xpath applied) and confirms the injected style block with
        the authoritative navy/gold actually appears in the output HTML."""
        company = self.env.company
        values = {
            "company": company,
            "o": company,
            "report_type": "pdf",
            "layout_document_title": "Test Document",
            "forced_vat": False,
            "display_name_in_footer": False,
        }
        html = self.env["ir.qweb"]._render("web.external_layout_standard", values)
        self.assertIn(NAVY, html)
        self.assertIn(GOLD, html)
        self.assertIn(".article h2", html)
        self.assertIn(".o_company_tagline", html)


@tagged("post_install", "-at_install")
class TestSgcThemeBackendHttp(HttpCase):
    """As close as reasonably possible (without a full visual-regression
    tool) to confirming the theme is wired into a REAL rendered backend
    page, not just compilable in isolation."""

    def test_backend_webclient_loads_with_theme_installed(self):
        self.authenticate("admin", "admin")
        response = self.url_open("/odoo")
        self.assertEqual(response.status_code, 200)
