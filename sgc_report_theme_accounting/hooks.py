# -*- coding: utf-8 -*-
"""Conditional bridge between the invoice report and the SGC layout.

The bridge re-points ``account.report_invoice_document`` at the SGC layout.
It cannot be a plain XML view any more: ``account_edi_ubl_cii`` (core Odoo
19, UAE e-invoicing) inherits the same template and rewrites the very same
call with a literal ``//t[@t-call='web.external_layout']`` XPath.

Odoo combines inherited views with EXTENSIONS FIRST and primaries after
(see ``ir.ui_view._combine``), so the bridge - an extension - always runs
before ``account_edi_ubl_cii``'s primary view. The bridge changes the
t-call, the core module then looks for the literal value that is no longer
there, and the whole registry load fails:

    Element '<xpath expr="//t[@t-call='web.external_layout']">' cannot be
    located in parent view

That aborts the database initialisation, which is far worse than an
invoice PDF that carries the stock layout instead of the SGC one.

So the bridge is created here instead of from XML, and only when it is
safe to do so:

* ``account_edi_ubl_cii`` NOT installed -> the bridge exists and the
  invoice PDF carries the SGC theme (the long-standing behaviour).
* ``account_edi_ubl_cii`` installed -> the bridge is removed, the UAE
  e-invoice layout wins, and the database loads.

The e-invoice XML is unaffected either way: it is generated server-side by
``account_edi_xml_cii_facturx._export_invoice``, not from this template.
"""
import logging

from odoo import api

_logger = logging.getLogger(__name__)

BRIDGE_XMLID = "sgc_report_theme_accounting.report_invoice_document_sgc"
BRIDGE_NAME = "report_invoice_document_sgc"
UAE_MODULE = "account_edi_ubl_cii"

# The root element must be <data>: that is what Odoo's XML loader produces
# for a <template inherit_id="..."> (it rewrites the tag to "data"), and the
# inheritance engine only unwraps a <data> root into spec nodes.
BRIDGE_ARCH = """
<data>
    <xpath expr="//t[contains(@t-call,'external_layout') or contains(@t-call,'internal_layout')]" position="attributes">
        <attribute name="t-call">sgc_report_theme_core.external_layout_sgc</attribute>
    </xpath>
</data>
"""


def _has_uae_edi(env):
    """True when the UAE e-invoicing module is installed or being installed."""
    return bool(env["ir.module.module"].sudo().search([
        ("name", "=", UAE_MODULE),
        ("state", "in", ("installed", "to install", "to upgrade")),
    ]))


def _arch_text(view):
    """The view arch as text. Odoo 19 returns a {lang: arch} mapping."""
    arch = view.arch or ""
    if isinstance(arch, dict):
        return " ".join(str(value) for value in arch.values())
    return str(arch)


def _arch_is_current(view):
    """True when the stored arch is the shape this module expects.

    The root must be <data> (Odoo's XML loader rewrites a
    <template inherit_id="..."> into <data>), and the XPath must be the
    tolerant one. Anything else - an older literal XPath, a <templates>
    root left over from an earlier shape - has to be rebuilt.
    """
    text = _arch_text(view)
    return (
        view.mode == "extension"
        and "<data" in text
        and "contains(@t-call" in text
    )


def _bridge_views(env):
    """Every view carrying the bridge key (there can be more than one after
    a half-applied upgrade, so they are all handled)."""
    return env["ir.ui.view"].sudo().search([("key", "=", BRIDGE_XMLID)])


def _drop_bridge(env, views):
    """Remove the bridge views and their xmlids."""
    if views:
        views.unlink()
    env["ir.model.data"].sudo().search([
        ("module", "=", "sgc_report_theme_accounting"),
        ("name", "=", BRIDGE_NAME),
        ("model", "=", "ir.ui.view"),
    ]).unlink()


def _create_bridge(env):
    """Create the bridge view and register its xmlid."""
    View = env["ir.ui.view"].sudo()
    parent = env.ref("account.report_invoice_document")
    new_view = View.create({
        "name": BRIDGE_NAME,
        "type": "qweb",
        "key": BRIDGE_XMLID,
        "inherit_id": parent.id,
        "mode": "extension",
        "priority": 99,
        "arch": BRIDGE_ARCH,
        "active": True,
    })
    env["ir.model.data"].sudo().create({
        "name": BRIDGE_NAME,
        "module": "sgc_report_theme_accounting",
        "model": "ir.ui.view",
        "res_id": new_view.id,
        "noupdate": True,
    })
    return new_view


def sync_invoice_bridge(env):
    """Create or drop the invoice bridge depending on what is installed.

    Returns True when the bridge is present afterwards.
    """
    views = _bridge_views(env)

    if _has_uae_edi(env):
        if views:
            _logger.info(
                "%s is installed: removing the SGC invoice bridge so the two "
                "layout rewrites cannot collide.", UAE_MODULE,
            )
            _drop_bridge(env, views)
        return False

    if views:
        # An upgraded database: keep one view, drop any duplicate, and make
        # sure it carries the tolerant XPath.
        view = views[0]
        if len(views) > 1:
            views[1:].unlink()
        if _arch_is_current(view):
            return True
        # The stored arch is an older shape: rebuild the view rather than
        # writing over it (writing validates the combined arch, which is
        # exactly what is broken).
        _logger.info("Rebuilding the SGC invoice bridge view.")
        _drop_bridge(env, view)
        _create_bridge(env)
        return True

    _logger.info("Creating the SGC invoice bridge view.")
    _create_bridge(env)
    return True


def post_init_hook(env):
    """Create the bridge at install time."""
    sync_invoice_bridge(env)
