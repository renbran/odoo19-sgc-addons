{
    "name": "SGC Report Theme - Core",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Foundation module for the SGC TECH AI report/email design system: fonts, "
                "design tokens, paperformats, the additive external_layout_sgc report "
                "layout, email_shell_sgc reusable email chrome, and reusable QWeb blocks.",
    "description": """
SGC Report Theme - Core
========================

Phase 1 foundation module of the SGC TECH AI Enterprise Publishing System
redesign (RALPLAN consensus plan, 2026-07-23).

This module is INTENTIONALLY a no-op for every existing REPORT:

- It never overrides ``web.external_layout`` or any stock layout
  (``external_layout_standard`` / ``_bold`` / ``_boxed`` / ``_clean``).
- It never writes ``res.company.external_report_layout_id`` or any other
  field the stock dispatcher reads.
- It contains zero ``inherit_id`` / ``t-call`` re-points of any EXISTING
  report template (core purity, statically assertable).
- All of its CSS rules are namespaced under ``.o_sgc_report`` (or exist only
  inside the ``external_layout_sgc`` template tree) so nothing it ships can
  leak into stock reports sharing the same asset bundle.
- Its ``@font-face`` declarations use the distinct family names
  ``'IBM Plex Sans'`` / ``'IBM Plex Serif'`` and never rebind a family name
  a stock template already references.

Installing this module alone should change the rendered output of NO
existing report. Actual re-pointing of specific reports onto the new
``external_layout_sgc`` layout happens per-wave in separate, thin
"bridge" modules (``sgc_report_theme_<category>``) added later, each
depending on this core module plus the specific business module(s) it
re-points.

2026-08-02: added ``email_shell_sgc`` (views/email_shell_sgc.xml), a
reusable QWeb "chrome" block for customer-facing transactional emails
(navy masthead, gold corner geometry, Dubai coordinate marks, deep-navy
footer band) - extracted from sgc_meeting_ai's already-live, already-
approved "Active Meeting Invitation (SGC)" template, which is the
established reference for this brand's email design. Unlike that
template (fully self-contained, no shared block), this shell lets other
mail.templates ``t-call`` it with their own content via the standard
QWeb slot pattern (content between the t-call tags, re-inserted via
``t-out="0"``), matching each t-call with ``t-set="doc_subtitle"`` for
the masthead's document-type line. Deliberately does NOT go through
``email_layout_xmlid``/the stock ``mail.mail_notification_layout`` at
all - the reference template proves that pattern isn't used for SGC's
branded transactional emails; a consuming template sets
``email_layout_xmlid = False`` instead, same as the reference.
""",
    "author": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": ["web", "mail"],
    "data": [
        "data/paperformat_data.xml",
        "data/document_layout_data.xml",
        "views/report_layout_sgc.xml",
        "views/report_blocks.xml",
        "views/email_shell_sgc.xml",
    ],
    # 2026-07-23 fix: web.report_assets_pdf does NOT automatically inline
    # web.report_assets_common's custom-module contributions - they are
    # compiled as separate, independent bundles (confirmed empirically: the
    # compiled report_assets_pdf.min.css attachment had an identical content
    # hash before and after this module was installed). wkhtmltopdf only
    # picks up report_assets_pdf, so our SCSS must be declared in BOTH
    # bundles, in the SAME file order in each, so sgc_report_tokens.scss's
    # variables stay in scope for sgc_report_blocks.scss within each bundle's
    # own independent compile pass. Neither bundle is web.assets_frontend,
    # web.assets_common, or web.assets_backend (D1 still holds).
    "assets": {
        "web.report_assets_common": [
            "sgc_report_theme_core/static/src/scss/sgc_report_fonts.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_tokens.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_grid.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_blocks.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_signature.scss",
            # 2026-07-28 print typography + content-aware density. Loaded LAST
            # so its rules win on equal specificity against the older block
            # styles it supersedes.
            "sgc_report_theme_core/static/src/scss/sgc_report.scss",
        ],
        "web.report_assets_pdf": [
            "sgc_report_theme_core/static/src/scss/sgc_report_fonts.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_tokens.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_grid.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_blocks.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report_signature.scss",
            "sgc_report_theme_core/static/src/scss/sgc_report.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
