# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
# =============================================================================
# Stage 3 tests — sgc_theme_common ("Aurum Design Tokens").
#
# This module ships NO python models and NO business logic: it is a pure
# shared SCSS/CSS design-token layer (spec §3). What actually matters for a
# module like this is:
#   1. it installs cleanly as the hidden "Technical" shared dependency
#      (spec §12 — NOT a Theme/* category, so it is never stripped from the
#      website's active-theme asset filtering);
#   2. the ONE token source file (_sgc_tokens.scss / _sgc_tokens_root.css)
#      carries the AUTHORITATIVE branding/SGC-BRAND.md hex values
#      (navy #0F2C4C / gold #C9A227 / cream #F5EFE0), NOT the stale
#      brand_asset/braand_prompt.md values (navy #1B3A57 / gold #C9A961 /
#      cream #F5F3EE) — spec §11;
#   3. those tokens actually propagate into BOTH the compiled backend
#      (web.assets_backend) and frontend (web.assets_frontend) asset
#      bundles, which is the entire point of the shared-token architecture
#      (spec §3.2, confirmed live in spec §12).
# =============================================================================

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# Authoritative hex (branding/SGC-BRAND.md, spec §11) — what MUST be present.
NAVY = "#0F2C4C"
GOLD = "#C9A227"
CREAM = "#F5EFE0"

# Stale hex from brand_asset/braand_prompt.md — must NOT govern the token
# layer (spec §9 item 1 / §11 resolution).
STALE_NAVY = "#1B3A57"
STALE_GOLD = "#C9A961"
STALE_CREAM = "#F5F3EE"


@tagged("post_install", "-at_install")
class TestSgcThemeCommonInstall(TransactionCase):
    """The module installs cleanly as a hidden shared dependency."""

    def test_module_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_common")])
        self.assertEqual(len(module), 1, "sgc_theme_common should be a known module")
        self.assertEqual(module.state, "installed")

    def test_module_is_hidden_technical_category_not_a_theme(self):
        """Stage 2 fix: category must NOT be Theme/* or Odoo's website asset
        pipeline (website/models/ir_asset.py::_get_active_addons_list) will
        silently strip it from every website page except the active theme."""
        module = self.env["ir.module.module"].search([("name", "=", "sgc_theme_common")])
        self.assertFalse(
            (module.category_id.name or "").startswith("Theme"),
            "sgc_theme_common must stay out of the Theme/* category tree "
            "(spec §12) so it loads unconditionally in both bundles.",
        )


@tagged("post_install", "-at_install")
class TestSgcThemeCommonStaticTokenFiles(TransactionCase):
    """Fast, compile-free spot checks directly on the single source-of-truth
    token files (no SCSS/asset compilation involved)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        module_path = get_module_path("sgc_theme_common")
        assert module_path, "sgc_theme_common module path must be resolvable"
        scss_path = os.path.join(module_path, "static", "src", "scss", "_sgc_tokens.scss")
        css_path = os.path.join(module_path, "static", "src", "css", "_sgc_tokens_root.css")
        assert os.path.isfile(scss_path) and os.path.isfile(css_path), "token source files must exist on disk"
        with open(scss_path, encoding="utf-8") as f:
            cls.scss_content = f.read()
        with open(css_path, encoding="utf-8") as f:
            cls.css_content = f.read()

    def test_scss_core_palette_uses_authoritative_hex(self):
        self.assertRegex(self.scss_content, r"\$sgc-navy:\s*#0F2C4C")
        self.assertRegex(self.scss_content, r"\$sgc-gold:\s*#C9A227")
        self.assertRegex(self.scss_content, r"\$sgc-cream:\s*#F5EFE0")

    def test_scss_does_not_use_stale_braand_prompt_hex(self):
        content_lower = self.scss_content.lower()
        for stale in (STALE_NAVY, STALE_GOLD, STALE_CREAM):
            self.assertNotIn(
                stale.lower(),
                content_lower,
                f"_sgc_tokens.scss must not carry the stale hex {stale} "
                "from brand_asset/braand_prompt.md (spec §11).",
            )

    def test_css_root_vars_mirror_authoritative_hex(self):
        self.assertRegex(self.css_content, r"--sgc-navy:\s*#0F2C4C;")
        self.assertRegex(self.css_content, r"--sgc-gold:\s*#C9A227;")
        self.assertRegex(self.css_content, r"--sgc-cream:\s*#F5EFE0;")

    def test_css_root_does_not_use_stale_braand_prompt_hex(self):
        content_lower = self.css_content.lower()
        for stale in (STALE_NAVY, STALE_GOLD, STALE_CREAM):
            self.assertNotIn(stale.lower(), content_lower)

    def test_css_root_gates_motion_tokens_on_reduced_motion(self):
        """Motion tokens must be neutralised under prefers-reduced-motion so
        ANY consumer reading --sgc-dur-* gets an instant state (spec §8)."""
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css_content)
        reduced_block = self.css_content.split("@media (prefers-reduced-motion: reduce)")[1]
        self.assertIn("--sgc-dur-fast: 0ms", reduced_block)
        self.assertIn("--sgc-dur-base: 0ms", reduced_block)
        self.assertIn("--sgc-dur-slow: 0ms", reduced_block)


@tagged("post_install", "-at_install")
class TestSgcThemeCommonBundlePropagation(TransactionCase):
    """Integration-level check: the tokens actually reach the COMPILED
    bundles both consuming themes read from (not just the source files)."""

    def _compiled_css(self, bundle_name):
        bundle = self.env["ir.qweb"]._get_asset_bundle(bundle_name, css=True, js=False)
        attachments = bundle.css()
        # bundle.css()/js() may return more than one ir.attachment (e.g. a
        # css.map sourcemap companion); concatenate raw content so substring
        # assertions below see everything regardless of record count.
        return b"\n".join(raw or b"" for raw in attachments.mapped("raw")).decode()

    def test_tokens_propagate_to_backend_bundle(self):
        css = self._compiled_css("web.assets_backend")
        self.assertIn(NAVY, css)
        self.assertIn(GOLD, css)
        self.assertIn(CREAM, css)
        for stale in (STALE_NAVY, STALE_GOLD, STALE_CREAM):
            self.assertNotIn(stale.lower(), css.lower())

    def test_tokens_propagate_to_frontend_bundle(self):
        css = self._compiled_css("web.assets_frontend")
        css_lower = css.lower()
        self.assertIn(NAVY.lower(), css_lower)
        self.assertIn(GOLD.lower(), css_lower)
        self.assertIn(CREAM.lower(), css_lower)
        for stale in (STALE_NAVY, STALE_GOLD, STALE_CREAM):
            self.assertNotIn(stale.lower(), css_lower)

    def test_tokens_root_css_file_present_in_both_bundles(self):
        """Confirms sgc_theme_common's OWN _sgc_tokens_root.css (the runtime
        CSS custom-properties mirror) is the thing that landed in both
        bundles, not just an unrelated re-derivation of the same hex."""
        backend_css = self._compiled_css("web.assets_backend")
        frontend_css = self._compiled_css("web.assets_frontend")
        root_var_pattern = re.compile(r"--sgc-navy:\s*#0F2C4C")
        self.assertRegex(backend_css, root_var_pattern)
        self.assertRegex(frontend_css, root_var_pattern)
