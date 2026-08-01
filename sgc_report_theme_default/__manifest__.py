# -*- coding: utf-8 -*-
# (c) SGC TECH AI (https://sgctech.ai)
{
    "name": "SGC Report Theme - Document Layout",
    "version": "19.0.1.0.0",
    "category": "Reporting",
    "summary": "Registers the SGC TECH AI layout as a selectable company "
               "Document Layout, so every report renders with SGC branding "
               "through Odoo's supported dispatcher - no view surgery.",
    "description": """
SGC Report Theme - Document Layout
===================================

The missing wire between ``sgc_report_theme_core`` (which ships the fonts,
tokens and ``external_layout_sgc`` template but is deliberately a no-op) and
the reports users actually print.

Why this module exists
----------------------
``sgc_report_theme_core`` intentionally never touches
``res.company.external_report_layout_id`` - a correct Phase 1 decision, but
it left the layout unreachable: installed, styled, and applied to nothing.

The obvious-but-wrong fix is to XPath-patch ``web.external_layout`` so every
report is forced through a custom template. ``sgc_construction_management``
did exactly that::

    <xpath expr="//t[@t-call]" position="replace">   <!-- DO NOT DO THIS -->

That replace stripped the ``t-if`` off the dispatcher's terminal
``t-if``/``t-else`` pair, orphaning the ``t-else``. QWeb then refused to
compile ``web.external_layout`` at all, and *every* PDF in the database
returned HTTP 500 (2026-08-01 incident: sale orders, pro-forma and customer
invoices all down until the offending view was removed).

The supported extension point
-----------------------------
Stock ``web.external_layout`` already dispatches to whatever layout the
company selects::

    <t t-call="{{company.external_report_layout_id.sudo().key
                 or 'web.external_layout_standard'}}">

So branding every report needs **no template modification at all** - only a
``report.layout`` record pointing at our view. That record is what populates
the *Settings > Companies > Document Layout* picker.

This module therefore ships exactly one data record and zero template
patches. ``web.external_layout`` is left byte-identical to stock, which is
what makes the 2026-08-01 failure mode structurally impossible here.

Why the record is declared in XML, not INSERTed
-----------------------------------------------
The pre-existing "SGC TECH AI Brand" layout row on production was written by
raw SQL: it had no ``create_uid``, no ``create_date``, and - critically - no
``ir_model_data`` row. With no XML ID, no module owned it, so Odoo could not
clean it up on uninstall; it survived as an orphan holding a foreign key to
a view the uninstall needed to delete, and blocked the uninstall outright.

Declaring the record here gives it an ``ir_model_data`` entry, so it is
created, updated and *removed* with the module like any other module data.

Activation is a deliberate manual step
--------------------------------------
Installing this module makes the layout **available**; it does not select it.
Silently rewriting a company's document layout at install time would restyle
every report in the database as an invisible side effect of an install - the
same class of surprise this module's docstring exists to prevent.

To activate: *Settings > General Settings > Companies > Document Layout* and
pick **SGC TECH AI**. To roll back, pick any stock layout - no uninstall
required, and no template is ever in an inconsistent state.
""",
    "author": "SGC TECH AI",
    "maintainer": "SGC TECH AI",
    "website": "https://sgctech.ai",
    "support": "info@sgctech.ai",
    "license": "LGPL-3",
    # sgc_report_theme_core supplies external_layout_sgc (the view this
    # record references) plus the fonts/tokens/blocks SCSS that style it.
    # web supplies the report.layout model and the dispatcher we rely on.
    "depends": ["web", "sgc_report_theme_core"],
    "data": [
        "data/paperformat_data.xml",
        "data/report_layout_data.xml",
    ],
    # sgc_report_theme_core already ships the fonts, tokens and block styles.
    # This module adds ONLY document-level refinements (header compaction,
    # line-item table, totals) in sgc_report_documents.scss.
    #
    # Declared in BOTH bundles for the reason sgc_report_theme_core documents
    # empirically: web.report_assets_pdf does not inline custom-module
    # contributions to web.report_assets_common - they compile as separate,
    # independent bundles, and wkhtmltopdf only loads report_assets_pdf.
    # Because each bundle compiles independently, this file must land AFTER
    # core's sgc_report_tokens.scss in each; module dependency order
    # (sgc_report_theme_core -> this module) guarantees that, which is what
    # keeps $sgc-navy and friends in scope here.
    "assets": {
        "web.report_assets_common": [
            "sgc_report_theme_default/static/src/scss/sgc_report_documents.scss",
        ],
        "web.report_assets_pdf": [
            "sgc_report_theme_default/static/src/scss/sgc_report_documents.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
