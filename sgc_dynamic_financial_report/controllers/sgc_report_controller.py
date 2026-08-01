# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

import json
import logging

from odoo import fields, http
from odoo.http import request

from odoo.addons.sgc_dynamic_financial_report.models.sgc_report_metadata import (
    get_full_registry,
    get_report_metadata,
)

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
        csrf=False,
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

    # ── Metadata registry (AJAX, drives the enterprise filter bar) ──────

    @http.route(
        "/sgc/dfr/metadata",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_full_metadata_registry(self, **kwargs):
        """Return the full metadata registry: every report's filter
        declaration plus the shared filter-widget definitions.

        The OWL enterprise filter bar fetches this once per session and
        caches it client-side; it re-reads only ``reports[report_type]``
        when the user switches report type, never re-fetching the shared
        ``filters`` definitions.
        """
        user = request.env.user
        if not user.has_group("sgc_dynamic_financial_report.sgc_dfr_group_user"):
            return {"error": "Access denied"}
        return get_full_registry()

    @http.route(
        "/sgc/dfr/metadata/<string:report_type>",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_report_metadata_endpoint(self, report_type, **kwargs):
        """Return the metadata declaration for a single ``report_type``.

        Used when the user switches the report-type dropdown and the
        filter bar needs only the new report's toolbar/more-filters
        declaration, not the whole registry.
        """
        user = request.env.user
        if not user.has_group("sgc_dynamic_financial_report.sgc_dfr_group_user"):
            return {"error": "Access denied"}
        metadata = get_report_metadata(report_type)
        if metadata is None:
            return {"error": "Unknown report type: %s" % report_type}
        return metadata

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

    # ── Drill-down endpoint (AJAX) ─────────────────────────────────────

    @http.route(
        "/sgc/dfr/drilldown/<int:wizard_id>/<int:account_id>",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def drilldown_data(self, wizard_id, account_id, **kwargs):
        """Return drill-down move lines for a single account.

        Calls ``sgc.financial.report.engine._get_drilldown_data()`` and
        returns the structured JSON result so the frontend can render a
        popup / modal table without a full page reload.

        Access checks (group + company) mirror the preview endpoint.
        """
        user = request.env.user
        if not user.has_group("sgc_dynamic_financial_report.sgc_dfr_group_user"):
            return {"error": "Access denied"}

        wizard = request.env["sgc.financial.report.wizard"].browse(wizard_id)
        if not wizard.exists():
            return {"error": "Wizard not found"}

        if wizard.company_id not in user.company_ids:
            return {"error": "Access denied"}

        try:
            engine = request.env["sgc.financial.report.engine"]
            data = engine._get_drilldown_data(wizard, account_id)
            if data is None:
                return {"error": "Account not found or access denied"}
            return data
        except Exception as exc:
            _logger.exception("SGC DFR: Drill-down failed for wizard %s account %s", wizard_id, account_id)
            return {"error": str(exc)}

    # ── BI API: read-only JSON endpoint for external BI integration ────

    @http.route(
        "/sgc/dfr/api/report/<int:wizard_id>",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def bi_api_report(self, wizard_id, **kwargs):
        """Read-only JSON endpoint for BI tools.

        Returns exactly the same data as the preview endpoint but as a
        structured JSON response (``generate=True`` causes the engine to
        return its full data dict) instead of HTML.  This is designed for
        external BI integration (Power BI, Tableau, custom dashboards).

        Applies the same group + company access checks as the interactive
        preview endpoint so that BI tokens inherit the user's Odoo ACLs.
        """
        user = request.env.user
        if not user.has_group("sgc_dynamic_financial_report.sgc_dfr_group_user"):
            return request.make_json_response(
                {"error": "Access denied"}, status=403,
            )

        wizard = request.env["sgc.financial.report.wizard"].browse(wizard_id)
        if not wizard.exists():
            return request.make_json_response(
                {"error": "Wizard not found"}, status=404,
            )

        if wizard.company_id not in user.company_ids:
            return request.make_json_response(
                {"error": "Access denied"}, status=403,
            )

        try:
            engine = request.env["sgc.financial.report.engine"]
            result = engine._generate_report(wizard)
            meta = {
                "wizard_id": wizard.id,
                "report_type": wizard.report_type,
                "company_id": wizard.company_id.id,
                "company_name": wizard.company_id.name,
                "date_from": fields.Date.to_string(wizard.date_from),
                "date_to": fields.Date.to_string(wizard.date_to),
                "currency": wizard.currency_id.name or wizard.company_id.currency_id.name,
                "generated_at": fields.Datetime.now().isoformat(),
            }
            result["_meta"] = meta
            return request.make_json_response(result)
        except Exception as exc:
            _logger.exception("SGC DFR: BI API failed for wizard %s", wizard_id)
            return request.make_json_response(
                {"error": str(exc)}, status=500,
            )