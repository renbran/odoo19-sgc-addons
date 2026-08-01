# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

"""Shared mixin for SGC XLSX financial reports.

Every concrete report (``report.sgc_dynamic_financial_report.*_xlsx``)
inherits from this mixin on top of ``report.report_xlsx.abstract`` so
that the polish features (logo, parameters summary, timestamp footer,
freeze panes, autofilter, page orientation, zebra striping) stay
consistent across all 9 reports without duplicating the boilerplate in
every file.

The mixin only exposes helper methods - it never overrides anything
from ``report.report_xlsx.abstract``, so the existing ``generate_xlsx_report``
contract is preserved and the report ``_name`` / ``binding_model_id``
stays untouched.
"""

import base64
from datetime import datetime

from odoo import fields, models


def _column_letter(col_idx):
    """Convert a 0-based column index to an Excel column letter."""
    result = []
    col_idx += 1
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        result.append(chr(65 + rem))
    return "".join(reversed(result))


class SgcFinancialReportXlsxMixin(models.AbstractModel):
    """Mixin that provides shared XLSX polish helpers.

    All 9 concrete XLSX reports (``sgc_balance_sheet_xlsx`` etc.) inherit
    from this in addition to ``report.report_xlsx.abstract``. The mixin
    keeps the report definitions thin while still applying the same
    visual treatment (logo, parameters, freeze, autofilter, zebra) to
    every export.
    """

    _name = "report.sgc_dynamic_financial_report.xlsx_mixin"
    _description = "SGC XLSX Report Mixin (Shared helpers)"
    # NOTE: No _inherit.  Each concrete report inherits from BOTH
    # report.report_xlsx.abstract AND this mixin independently.  If this
    # mixin itself inherits from report_xlsx.abstract, Python's MRO cannot
    # resolve the diamond (report_xlsx.abstract appears twice in the
    # chain) and raises TypeError on module load.

    # ── Format builders ─────────────────────────────────────────────
    def _sgc_xlsx_build_formats(self, workbook):
        """Return a dict of named xlsxwriter formats used by all reports.

        Centralised so that every report reuses the same colour palette
        and number format. xlsxwriter dedups identical format specs on
        its side, so always calling ``add_format`` here is cheap.
        """
        return {
            "title": workbook.add_format({
                "bold": True, "size": 14, "valign": "vcenter",
            }),
            "subtitle": workbook.add_format({
                "bold": True, "size": 11, "valign": "vcenter",
            }),
            "date": workbook.add_format({
                "size": 10, "valign": "vcenter",
            }),
            "params": workbook.add_format({
                "size": 9, "italic": True, "valign": "vcenter",
                "text_wrap": True,
            }),
            "footer": workbook.add_format({
                "size": 8, "italic": True, "font_color": "#6c757d",
                "align": "left", "valign": "vcenter",
            }),
            "col_header": workbook.add_format({
                "bold": True, "size": 10, "bg_color": "#4472C4",
                "font_color": "#FFFFFF", "border": 1, "text_wrap": True,
                "valign": "vcenter", "align": "center",
            }),
            "section_header": workbook.add_format({
                "bold": True, "size": 11, "bg_color": "#D9E2F3",
                "border": 1, "valign": "vcenter",
            }),
            "normal": workbook.add_format({
                "size": 10, "valign": "vcenter",
            }),
            # Zebra-striping variants: every other row gets a faint grey
            # background for readability without losing the official
            # header colour.
            "zebra_text": workbook.add_format({
                "size": 10, "valign": "vcenter", "bg_color": "#F2F2F2",
            }),
            "money": workbook.add_format({
                "num_format": "#,##0.00", "valign": "vcenter",
            }),
            "money_zebra": workbook.add_format({
                "num_format": "#,##0.00", "valign": "vcenter",
                "bg_color": "#F2F2F2",
            }),
            "date_value": workbook.add_format({
                "size": 10, "num_format": "YYYY-MM-DD", "valign": "vcenter",
            }),
            "date_value_zebra": workbook.add_format({
                "size": 10, "num_format": "YYYY-MM-DD", "valign": "vcenter",
                "bg_color": "#F2F2F2",
            }),
            "pct": workbook.add_format({
                "num_format": "0.00%", "valign": "vcenter",
            }),
            "subtotal": workbook.add_format({
                "bold": True, "size": 10, "top": 2, "valign": "vcenter",
            }),
            "subtotal_money": workbook.add_format({
                "bold": True, "size": 10, "top": 2,
                "num_format": "#,##0.00", "valign": "vcenter",
            }),
            "total": workbook.add_format({
                "bold": True, "size": 11, "top": 2, "bottom": 2,
                "valign": "vcenter",
            }),
            "total_money": workbook.add_format({
                "bold": True, "size": 11, "top": 2, "bottom": 2,
                "num_format": "#,##0.00", "valign": "vcenter",
            }),
            "grand_total": workbook.add_format({
                "bold": True, "size": 12, "top": 2, "bottom": 2,
                "valign": "vcenter", "bg_color": "#FFE699",
            }),
            "grand_total_money": workbook.add_format({
                "bold": True, "size": 12, "top": 2, "bottom": 2,
                "num_format": "#,##0.00", "valign": "vcenter",
                "bg_color": "#FFE699",
            }),
        }

    # ── Page / freeze / autofilter helpers ──────────────────────────
    def _sgc_xlsx_apply_page_setup(self, sheet, orientation="portrait"):
        """Set page orientation, fit-to-page and print margins.

        Defaults to ``portrait``; the wide reports (General Ledger,
        Partner Ledger, Trial Balance) pass ``landscape`` so all their
        columns fit on a printed A4.
        """
        sheet.set_landscape() if orientation == "landscape" else sheet.set_portrait()
        sheet.set_paper(9)  # A4
        sheet.fit_to_pages(1, 0)  # fit horizontally; vertical = unbounded
        sheet.set_margins(0.5, 0.5, 0.5, 0.5)
        sheet.center_horizontally()
        sheet.set_header(
            "&L&\"-,Bold\"&12SGC Financial Report"
            "&R&\"-,Italic\"&10&D &T"
        )
        sheet.set_footer(
            "&L&\"-,Italic\"&8Generated by SGC Dynamic Financial Reports"
            "&R&\"-,Italic\"&8Page &P of &N"
        )

    def _sgc_xlsx_apply_freeze(self, sheet, header_row=4, col_count=0):
        """Freeze the header row + first N columns (defaults to row only)."""
        sheet.freeze_panes(header_row + 1, col_count)

    def _sgc_xlsx_apply_autofilter(self, sheet, first_row, last_row, last_col_idx):
        """Add Excel's drop-down autofilter on the header range.

        Uses integer positional args (``first_row, last_row, 0, last_col_idx``)
        so xlsxwriter gets the correct 0-based row and column indices, avoiding
        the invalid string range that ``"5:5"`` (no columns) would produce.
        """
        sheet.autofilter(first_row, last_row, 0, last_col_idx)

    # ── Header / footer / parameters block ──────────────────────────
    def _sgc_xlsx_get_company_logo_bytes(self, wizard):
        """Return decoded PNG/JPEG bytes for the company logo, or ``b""``.

        Prefers ``company.sgc_dfr_logo`` (the per-company SGC override)
        and falls back to ``company.logo``. Returns ``b""`` if neither is
        set so callers can skip the image insertion.
        """
        company = wizard.company_id
        candidate = company.sgc_dfr_logo or company.logo
        if not candidate:
            return b""
        try:
            return base64.b64decode(candidate)
        except Exception:
            return b""

    def _sgc_xlsx_write_header_block(
        self, sheet, workbook, wizard, title, formats,
        column_count, header_row=0,
    ):
        """Write the report header (logo + title + date range + params).

        Layout (rows 0-based):
            row 0:  [Logo]  Company name (title)
            row 1:           Report title (subtitle)
            row 2:           Date range
            row 3:           Parameters summary (italic)
            row 4:           (blank)
            row 5:           column headers

        Returns the row index of the column-header row so callers can
        continue writing data below it.
        """
        company = wizard.company_id
        logo_bytes = self._sgc_xlsx_get_company_logo_bytes(wizard)
        title_text = company.name or ""
        subtitle_text = title or ""
        date_range = (
            f"From {fields.Date.to_string(wizard.date_from)} "
            f"to {fields.Date.to_string(wizard.date_to)}"
        )

        if logo_bytes:
            try:
                sheet.insert_image(
                    header_row, 0, "logo.png",
                    {"image_data": _BytesIO(logo_bytes), "x_scale": 0.5,
                     "y_scale": 0.5},
                )
            except Exception:
                # xlsxwriter raises on unsupported formats; fall back
                # silently so the export still succeeds.
                pass
        sheet.write(header_row, 1, title_text, formats["title"])
        sheet.write(header_row + 1, 1, subtitle_text, formats["subtitle"])
        sheet.write(header_row + 2, 1, date_range, formats["date"])
        params_text = self._sgc_xlsx_build_params_text(wizard)
        sheet.write(header_row + 3, 1, params_text, formats["params"])
        sheet.set_row(header_row, 28)
        sheet.set_row(header_row + 1, 22)
        return header_row + 5  # blank row, then column headers

    def _sgc_xlsx_build_params_text(self, wizard):
        """Build the report-parameters summary string for the header."""
        parts = []
        parts.append(f"Company: {wizard.company_id.name}")
        parts.append(f"Currency: {wizard.currency_id.name or wizard.company_id.currency_id.name}")
        parts.append(f"Target Moves: {dict(wizard._fields['target_move'].selection).get(wizard.target_move, wizard.target_move)}")
        if wizard.journal_ids:
            parts.append(f"Journals: {', '.join(wizard.journal_ids.mapped('name'))[:60]}")
        if wizard.account_ids:
            parts.append(f"Accounts: {len(wizard.account_ids)} selected")
        if wizard.partner_ids:
            parts.append(f"Partners: {len(wizard.partner_ids)} selected")
        if wizard.analytic_account_ids:
            parts.append(f"Analytic: {len(wizard.analytic_account_ids)} selected")
        if wizard.consolidate_companies:
            parts.append("Multi-Company: ON")
        if getattr(wizard, "show_budget_vs_actual", False):
            parts.append("Budget vs Actual: ON")
        if getattr(wizard, "analytic_breakdown", False):
            parts.append("Analytic Breakdown: ON")
        return " | ".join(parts)

    def _sgc_xlsx_write_footer_block(self, sheet, formats, footer_row, col_count):
        """Write the generation-timestamp footer at ``footer_row``.

        Adds a thin top border to the footer row and emits
        "Generated on <UTC ISO>" + report name on the left.
        """
        gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        footer_text = (
            f"Generated on {gen_time}  |  "
            f"SGC Dynamic Financial Reports  |  "
            f"All amounts in functional currency unless noted"
        )
        sheet.merge_range(
            footer_row, 0, footer_row, col_count - 1,
            footer_text, formats["footer"],
        )
        sheet.set_row(footer_row, 16)

    # ── Zebra-stripping helper ──────────────────────────────────────
    def _sgc_xlsx_zebra_format(self, formats, is_zebra_row, money=False, date=False):
        """Return the alternating ``normal``/``zebra`` xlsxwriter format."""
        if money:
            return formats["money_zebra"] if is_zebra_row else formats["money"]
        if date:
            return formats["date_value_zebra"] if is_zebra_row else formats["date_value"]
        return formats["zebra_text"] if is_zebra_row else formats["normal"]

    # ── Convenience: autosize columns from content ──────────────────
    def _sgc_xlsx_autosize_columns(self, sheet, sample_rows, max_width=42):
        """Set each column width to fit the longest cell in ``sample_rows``.

        ``sample_rows`` is a list of dicts (one per row). Columns not
        present in any row default to 12. Each width is capped at
        ``max_width`` so very long account names don't blow up the page
        layout.
        """
        widths = {}
        for row in sample_rows:
            for key, value in row.items():
                text = "" if value is None else str(value)
                widths[key] = max(widths.get(key, 0), len(text))
        col_idx = 0
        for key, length in widths.items():
            width = min(max(length + 2, 10), max_width)
            sheet.set_column(col_idx, col_idx, width)
            col_idx += 1

    # ── Column letter helper exposed for callers ────────────────────
    def _sgc_xlsx_col_letter(self, col_idx):
        return _column_letter(col_idx)


class _BytesIO:
    """Tiny file-like wrapper so xlsxwriter can read decoded logo bytes."""

    def __init__(self, data):
        self._data = data

    def read(self, *args, **kwargs):
        return self._data

    def seek(self, *args, **kwargs):
        return 0