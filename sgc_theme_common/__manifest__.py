# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
{
    "name": "Aurum Design Tokens",
    "summary": "Shared SGC design-token layer for the Aurum theme family",
    "description": """
Aurum Design Tokens
===================

The single source of truth for the SGC "Aurum" visual language: colours,
type scale, spacing, radius, shadow and motion timings.

This is a small shared dependency used by the Aurum Backend Theme and the
Aurum Website Theme so a dense data UI and a marketing site read as one
family. It ships:

* ``_sgc_tokens.scss`` — SCSS design tokens injected into
  ``web._assets_primary_variables`` (available to both the backend and the
  frontend SCSS compilation contexts).
* ``_sgc_tokens_root.css`` — the same tokens mirrored as CSS custom
  properties on ``:root`` for runtime use by JS / OWL components / snippet
  animations, loaded in both the backend and frontend bundles.

Edit the tokens in one place; both themes stay in sync.
""",
    "author": "SGC TECH",
    "maintainer": "SGC TECH",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    # NOT a "Theme/*" category on purpose: Odoo's website asset pipeline
    # (website/models/ir_asset.py::_get_active_addons_list) discards every theme
    # module except the website's active theme_id. As the shared token layer must
    # load unconditionally in BOTH the backend and frontend bundles, it uses the
    # non-theme "Technical" (hidden) category, which get_themes_domain() excludes.
    "category": "Technical",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [],
    "assets": {
        # SCSS token variables — injected before Bootstrap compilation and read
        # by BOTH the backend and frontend SCSS contexts.
        "web._assets_primary_variables": [
            "sgc_theme_common/static/src/scss/_sgc_tokens.scss",
        ],
        # Runtime CSS custom-properties mirror — identical file in both contexts.
        "web.assets_backend": [
            "sgc_theme_common/static/src/css/_sgc_tokens_root.css",
        ],
        "web.assets_frontend": [
            "sgc_theme_common/static/src/css/_sgc_tokens_root.css",
        ],
    },
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
