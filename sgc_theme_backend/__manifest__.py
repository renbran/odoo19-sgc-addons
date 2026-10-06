# -*- coding: utf-8 -*-
# (c) SGC TECH — Finance. Systems. Technology. — https://sgctech.ai
{
    "name": "Aurum Backend Theme",
    "summary": "Calm, high-contrast SGC skin for the Odoo 19 web client",
    "description": """
Aurum Backend Theme
===================

A calm, high-contrast restyle of the Odoo 19 web client — forms, lists,
kanban, search and printed reports — in the SGC navy / gold / cream palette
with elegant serif headings.

Design principles
-----------------
* **Readability first.** WCAG-AA contrast on text, rows, borders and status
  colours. Nothing here slows down data entry.
* **No 3D, no heavy animation.** Only subtle, fast (<=150ms) hover/focus/active
  micro-transitions, and every one of them is disabled under
  ``prefers-reduced-motion``.
* **Behaviour-safe.** Pure CSS/SCSS restyle — no OWL component overrides and no
  surgery on core views.

Includes
--------
* Global palette skin (navbar, canvas, accents)
* Form / list / kanban / search restyles
* AA-contrast buttons and status badges
* Dialog, tooltip and notification restyle
* Density-safe spacing
* A light, print-safe SGC accent on business reports

Part of the Aurum theme family (shares the Aurum Design Tokens layer).
""",
    "author": "SGC TECH",
    "maintainer": "SGC TECH",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    "category": "Theme/Backend",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "depends": ["web", "sgc_theme_common"],
    "data": [
        "views/report_layout.xml",
    ],
    "assets": {
        # Brand-colour overrides loaded BEFORE Odoo's own primary variables so
        # the whole `!default` cascade (brand-primary, button maps, etc.)
        # recomputes from the SGC navy/gold palette.
        "web._assets_primary_variables": [
            (
                "before",
                "web/static/src/scss/primary_variables.scss",
                "sgc_theme_backend/static/src/scss/backend_variables.scss",
            ),
        ],
        # The restyle itself lives ONLY in the backend bundle — it never leaks
        # into web.assets_frontend.
        "web.assets_backend": [
            "sgc_theme_backend/static/src/scss/backend_theme.scss",
        ],
    },
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
