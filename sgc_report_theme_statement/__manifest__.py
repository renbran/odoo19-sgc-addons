{
    "name": "SGC Report Theme - Statement Bridge",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Wave 1 bridge: re-points the Partner Statement report onto the "
                "SGC TECH AI external_layout_sgc layout.",
    "description": """
SGC Report Theme - Statement Bridge
=====================================

Thin, per-category bridge module (RALPLAN consensus plan, 2026-07-23,
Phase 2 / Wave 1: low-risk internal documents).

This module contains exactly ONE change: it re-points
``statement_report.res_partner_statement_report_template`` from
``t-call="web.external_layout"`` to
``t-call="sgc_report_theme_core.external_layout_sgc"`` via a single
``inherit_id`` view, and adds the ``o_sgc_table`` styling class to the
report's two data tables. No value-rendering expression (``t-esc`` /
``t-field`` / ``t-out``) is touched - every number, date, and text value
in the report is rendered by the exact same expression as before.

N3 invariant: ``res_partner_statement_report_template`` is not shared with
any other bridge - it is the sole report using this template, so
uninstalling this module reverts only this one report to its stock
layout, with no effect on any other report.

Depends on ``statement_report`` (the module owning the template being
re-pointed) and ``sgc_report_theme_core`` (the additive layout + blocks).
If ``statement_report`` is absent, this module is simply not installable
(declared dependency) - never a hard install failure.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["sgc_report_theme_core", "statement_report"],
    "data": [
        "views/res_partner_statement_bridge.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
