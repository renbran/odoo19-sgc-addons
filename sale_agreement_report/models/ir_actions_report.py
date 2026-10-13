# -*- coding: utf-8 -*-
"""Append the signed engagement agreement to the quotation PDF.

The agreement is stored as a PDF attachment on the sale order. When the standard
quotation report (sale.report_saleorder) is rendered for a single order, the agreement
pages are appended so the customer receives and signs a single document.
"""
import io
import logging

from odoo import models

_logger = logging.getLogger(__name__)

QUOTATION_REPORT = "sale.report_saleorder"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        content, report_type = super()._render_qweb_pdf(report_ref, res_ids, data)
        if report_type == "pdf" and res_ids and len(res_ids) == 1:
            try:
                report = self._get_report(report_ref)
                if report.report_name == QUOTATION_REPORT:
                    merged = self._sgc_merge_agreement(content, res_ids[0])
                    if merged:
                        content = merged
            except Exception:  # noqa: BLE001 - never break the quotation report
                _logger.exception("Could not append the agreement to the quotation PDF")
        return content, report_type

    def _sgc_merge_agreement(self, content, order_id):
        attachment = self.env["ir.attachment"].sudo().search(
            [
                ("res_model", "=", "sale.order"),
                ("res_id", "=", order_id),
                ("mimetype", "=", "application/pdf"),
                ("name", "ilike", "agreement"),
            ],
            limit=1,
            order="id desc",
        )
        if not attachment:
            return None
        try:
            from PyPDF2 import PdfReader, PdfWriter
        except ImportError:
            _logger.warning("PyPDF2 is not available; the agreement is not appended.")
            return None
        writer = PdfWriter()
        for page in PdfReader(io.BytesIO(content)).pages:
            writer.add_page(page)
        for page in PdfReader(io.BytesIO(attachment.raw)).pages:
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()