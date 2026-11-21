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

BRIDGE_ARCH = """
<templates inherit_id="account.report_invoice_document">
    <xpath expr="//t[contains(@t-call,'external_layout') or contains(@t-call,'internal_layout')]" position="attributes">
        <attribute name="t-call">sgc_report_theme_core.external_layout_sgc</attribute>
    </xpath>
</templates>
"""


def _has_uae_edi(env):
    """True when the UAE e-invoicing module is installed or being installed."""
    return bool(env["ir.module.module"].sudo().search([
        ("name", "=", UAE_MODULE),
        ("state", "in", ("installed", "to install", "to upgrade")),
    ]))


def _find_bridge(env):
    """Return the bridge view and its ir.model.data record, if any."""
    data = env["ir.model.data"].sudo().search([
        ("module", "=", "sgc_report_theme_accounting"),
        ("name", "=", BRIDGE_NAME),
        ("model", "=", "ir.ui.view"),
    ], limit=1)
    if not data:
        return env["ir.ui.view"].browse(), data
    view = env["ir.ui.view"].sudo().browse(data.res_id)
    if not view.exists():
        return env["ir.ui.view"].browse(), data
    return view, data


def sync_invoice_bridge(env):
    """Create or drop the invoice bridge depending on what is installed.

    Returns True when the bridge is present afterwards.
    """
    view, data = _find_bridge(env)
    View = env["ir.ui.view"].sudo()

    if _has_uae_edi(env):
        if view:
            _logger.info(
                "%s is installed: removing the SGC invoice bridge so the two "
                "layout rewrites cannot collide.", UAE_MODULE,
            )
            view.unlink()
            data.unlink()
        return False

    if view:
        # Already there (an upgraded database): keep it an extension and make
        # sure it carries the tolerant XPath.
        needs_update = (
            view.mode != "extension"
            or "contains(@t-call" not in (view.arch or "")
        )
        if needs_update:
            _logger.info("Refreshing the SGC invoice bridge view.")
            view.write({
                "mode": "extension",
                "priority": 99,
                "arch": BRIDGE_ARCH,
            })
        return True

    _logger.info("Creating the SGC invoice bridge view.")
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
    return True


def post_init_hook(env):
    """Create the bridge at install time."""
    sync_invoice_bridge(env)
