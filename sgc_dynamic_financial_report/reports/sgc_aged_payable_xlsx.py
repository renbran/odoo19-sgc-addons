# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcAgedPayableXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Aged Payable report."""

    _name = "report.sgc_dynamic_financial_report.sgc_aged_payable_xlsx"
    _description = "SGC Aged Payable XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Aged_Payable"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Aged Payable Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        # ── Fetch data from the report engine ───────────────────────
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        rows = report_data.get("rows", [])
        buckets = report_data.get("buckets", [])
        totals = report_data.get("totals", {})

        # ── Date range formatting ───────────────────────────────────
        date_from = wizard.date_from or ""
        date_to = wizard.date_to or ""
        date_range = f"From {date_from} to {date_to}"

        # ── Formats ─────────────────────────────────────────────────
        fmt_title = workbook.add_format({
            "bold": True,
            "size": 14,
            "valign": "vcenter",
        })
        fmt_date = workbook.add_format({
            "size": 10,
            "valign": "vcenter",
        })
        fmt_col_header = workbook.add_format({
            "bold": True,
            "size": 10,
            "bg_color": "#4472C4",
            "font_color": "#FFFFFF",
            "border": 1,
            "text_wrap": True,
            "valign": "vcenter",
            "align": "center",
        })
        fmt_normal = workbook.add_format({
            "size": 10,
            "valign": "vcenter",
        })
        fmt_money = workbook.add_format({
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })
        fmt_total = workbook.add_format({
            "bold": True,
            "size": 11,
            "top": 2,
            "bottom": 2,
            "valign": "vcenter",
        })
        fmt_total_money = workbook.add_format({
            "bold": True,
            "size": 11,
            "top": 2,
            "bottom": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })

        # ── Sheet setup ─────────────────────────────────────────────
        sheet = workbook.add_worksheet("Aged Payable")

        # Static columns: Partner(0), Ref(1), # Invoices(2)
        # Then dynamic bucket columns, then Total Balance
        num_buckets = len(buckets)
        total_col = 3 + num_buckets  # column index for Total Balance

        # Column widths
        sheet.set_column("A:A", 35)   # Partner
        sheet.set_column("B:B", 18)   # Ref
        sheet.set_column("C:C", 14)   # # Invoices
        for i in range(num_buckets):
            col_letter = chr(68 + i) if (68 + i) <= 90 else (
                "A" + chr(65 + (68 + i) - 91)
            )
            sheet.set_column(f"{col_letter}:{col_letter}", 16)
        # Total Balance column
        total_col_letter = chr(65 + total_col) if (65 + total_col) <= 90 else (
            "A" + chr(65 + (65 + total_col) - 91)
        )
        sheet.set_column(f"{total_col_letter}:{total_col_letter}", 18)

        # ── Report header (rows 0-2) ────────────────────────────────
        sheet.write(0, 0, wizard.company_id.name or "", fmt_title)
        sheet.write(1, 0, "Aged Payable Report", fmt_title)
        sheet.write(2, 0, date_range, fmt_date)

        # ── Column headers (row 4) ──────────────────────────────────
        row = 4
        col_headers = ["Partner", "Ref", "# Invoices"]
        for bucket in buckets:
            col_headers.append(bucket.get("label", ""))
        col_headers.append("Total Balance")
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Partner rows (row 5+) ───────────────────────────────────
        for partner_row in rows:
            sheet.write(row, 0, partner_row.get("partner_name") or "", fmt_normal)
            sheet.write(row, 1, partner_row.get("partner_ref") or "", fmt_normal)
            sheet.write(row, 2, partner_row.get("invoice_count", 0), fmt_normal)

            for b_idx, bucket in enumerate(buckets):
                label = bucket.get("label", "")
                value = float(partner_row.get(label, 0.0))
                sheet.write(row, 3 + b_idx, value, fmt_money)

            total_balance = float(partner_row.get("total_balance", 0.0))
            sheet.write(row, total_col, total_balance, fmt_money)
            row += 1

        # ── Totals row ──────────────────────────────────────────────
        sheet.write(row, 0, "", fmt_total)
        sheet.write(row, 1, "", fmt_total)
        sheet.write(row, 2, "", fmt_total)
        for b_idx, bucket in enumerate(buckets):
            label = bucket.get("label", "")
            value = float(totals.get(label, 0.0))
            sheet.write(row, 3 + b_idx, value, fmt_total_money)
        grand_total = float(totals.get("total_balance", 0.0))
        sheet.write(row, total_col, grand_total, fmt_total_money)