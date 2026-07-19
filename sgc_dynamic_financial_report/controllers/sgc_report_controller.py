# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

import json
import logging

from odoo import http
from odoo.http import content_disposition, request

_logger = logging.getLogger(__name__)


class SgcReportController(http.Controller):
    """HTTP controller for SGC Dynamic Financial Reports.

    Provides JSON endpoints for real-time report preview (used by the
    frontend widget) and optional PDF rendering.
    """

    # ── Report preview (AJAX) ────────────────────────────────────────

    @http.route(
        "/sgc/dfr/preview/<int:wizard_id>",
        type="http",
        auth="user",
        methods=["POST"],
    )
    def preview_report(self, wizard_id, **kwargs):
        """Return the report HTML as JSON for in-browser preview.

        This endpoint is called by the frontend widget after the wizard
        form is submitted.  The wizard's ``action_generate_report`` method
        is invoked server-side, and the resulting HTML is returned as a
        JSON payload.

        Args:
            wizard_id: ID of the ``sgc.financial.report.wizard`` record.

        Returns:
            JSON response with ``{'html': '<div>...</div>'}``.
        """
        user = request.env.user
        if not user.has_group("sgc_dynamic_financial_report.sgc_dfr_group_user"):
            return request.make_json_response(
                {"error": "Access denied"}, status=403
            )

        wizard = request.env["sgc.financial.report.wizard"].browse(wizard_id)
        if not wizard.exists():
            return request.make_json_response(
                {"error": "Wizard record not found"}, status=404
            )

        # A wizard belongs to whichever company it was generated for - a
        # user must not be able to pull another company's financial report
        # just by guessing/enumerating a wizard_id.
        if wizard.company_id not in user.company_ids:
            return request.make_json_response(
                {"error": "Access denied"}, status=403
            )

        try:
            engine = request.env["sgc.financial.report.engine"]
            result = engine._generate_report(wizard)
            return request.make_json_response(result)
        except Exception as exc:
            _logger.exception("SGC DFR: Failed to generate preview for wizard %s", wizard_id)
            return request.make_json_response(
                {"error": str(exc)}, status=500
            )

    # ── Account type mapping lookup (AJAX) ───────────────────────────

    @http.route(
        "/sgc/dfr/account_type_mapping",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_account_type_mapping(self, **kwargs):
        """Return the full account type → financial section mapping.

        Used by the frontend widget to populate dropdown filters.

        Returns:
            list of dicts: ``[{id, account_type, account_type_name, financial_section}, ...]``
        """
        mappings = request.env["sgc.dfr.account.type"].search_read(
            domain=[("active", "=", True)],
            fields=["id", "account_type", "financial_section"],
            order="sequence, id",
        )
        selection_labels = dict(
            request.env["sgc.dfr.account.type"]._fields["account_type"].selection
        )
        result = []
        for m in mappings:
            result.append({
                "id": m["id"],
                "account_type": m["account_type"],
                "account_type_name": selection_labels.get(m["account_type"], m["account_type"]),
                "financial_section": m["financial_section"],
            })
        return result