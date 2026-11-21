# -*- coding: utf-8 -*-
"""Maintenance model for the conditional invoice-report bridge."""
import logging

from odoo import api, fields, models

from ..hooks import sync_invoice_bridge

_logger = logging.getLogger(__name__)


class SgcReportThemeBridge(models.Model):
    """Keeps the SGC invoice bridge in step with what is installed.

    The bridge cannot live in XML because it must yield to
    ``account_edi_ubl_cii`` (see ``hooks``). This model exposes the sync so
    it can be run by hand, and by a daily cron so that installing or
    removing the UAE e-invoicing module later is picked up automatically.
    """

    _name = "sgc.report.theme.bridge"
    _description = "SGC Report Theme Bridge"

    name = fields.Char(default="SGC invoice report bridge")

    @api.model
    def action_sync_bridges(self):
        """Reconcile the bridge views with the installed modules."""
        present = sync_invoice_bridge(self.env)
        message = (
            "The SGC invoice bridge is active: invoice PDFs carry the SGC "
            "theme." if present else
            "The SGC invoice bridge is inactive because %s is installed: "
            "invoice PDFs keep the UAE e-invoice layout." % "account_edi_ubl_cii"
        )
        _logger.info(message)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "SGC report theme",
                "message": message,
                "type": "success",
            },
        }

    @api.model
    def _cron_sync_bridges(self):
        """Daily: keep the bridges in step with the installed modules."""
        try:
            sync_invoice_bridge(self.env)
        except Exception:
            _logger.exception("Could not synchronise the SGC report bridges")
