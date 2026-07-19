# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models
from collections import OrderedDict


class SgcTaxReportXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Tax Report."""

    _name = "report.sgc_dynamic_financial_report.sgc_tax_report_xlsx"
    _description = "SGC Tax Report XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Tax_Report"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Tax Report Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        # ── Fetch data from the report engine ───────────────────────
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        taxes = report_data.get("taxes", [])
        total_net = float(report_data.get("total_net", 0.0))
        total_tax = float(report_data.get("total_tax", 0.0))

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
        fmt_section_header = workbook.add_format({
            "bold": True,
            "size": 11,
            "bg_color": "#D9E2F3",
            "border": 1,
            "valign": "vcenter",
        })
        fmt_normal = workbook.add_format({
            "size": 10,
            "valign": "vcenter",
        })
        fmt_money = workbook.add_format({
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })
        fmt_pct = workbook.add_format({
            "num_format": "0.00%",
            "valign": "vcenter",
        })
        fmt_subtotal = workbook.add_format({
            "bold": True,
            "size": 10,
            "top": 2,
            "valign": "vcenter",
        })
        fmt_subtotal_money = workbook.add_format({
            "bold": True,
            "size": 10,
            "top": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })
        fmt_grand_total = workbook.add_format({
            "bold": True,
            "size": 11,
            "top": 2,
            "bottom": 2,
            "valign": "vcenter",
        })
        fmt_grand_total_money = workbook.add_format({
            "bold": True,
            "size": 11,
            "top": 2,
            "bottom": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })

        # ── Sheet setup ─────────────────────────────────────────────
        sheet = workbook.add_worksheet("Tax Report")

        # Columns: Tax Name(0) | Description(1) | Rate %(2) | Type(3) | Net Amount(4) | Tax Amount(5)
        sheet.set_column("A:A", 30)   # Tax Name
        sheet.set_column("B:B", 40)   # Description
        sheet.set_column("C:C", 12)   # Rate %
        sheet.set_column("D:D", 25)   # Type
        sheet.set_column("E:E", 18)   # Net Amount
        sheet.set_column("F:F", 18)   # Tax Amount

        # ── Report header (rows 0-2) ────────────────────────────────
        sheet.write(0, 0, wizard.company_id.name or "", fmt_title)
        sheet.write(1, 0, "Tax Report", fmt_title)
        sheet.write(2, 0, date_range, fmt_date)

        # ── Column headers (row 4) ──────────────────────────────────
        row = 4
        col_headers = [
            "Tax Name",
            "Description",
            "Rate %",
            "Type",
            "Net Amount",
            "Tax Amount",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Group taxes by tax_type ─────────────────────────────────
        type_labels = OrderedDict()
        type_labels["sale"] = "Sales Tax (Output)"
        type_labels["purchase"] = "Purchase Tax (Input)"
        type_labels["other"] = "Other"

        grouped = OrderedDict()
        for key in type_labels:
            grouped[key] = []

        for tax in taxes:
            tax_type = (tax.get("tax_type") or "").strip().lower()
            if tax_type not in grouped:
                tax_type = "other"
            grouped[tax_type].append(tax)

        # ── Write grouped sections ──────────────────────────────────
        for type_key, type_label in type_labels.items():
            section_taxes = grouped.get(type_key, [])
            if not section_taxes:
                continue

            # Section header row
            sheet.write(row, 0, type_label, fmt_section_header)
            sheet.write(row, 1, "", fmt_section_header)
            sheet.write(row, 2, "", fmt_section_header)
            sheet.write(row, 3, "", fmt_section_header)
            sheet.write(row, 4, "", fmt_section_header)
            sheet.write(row, 5, "", fmt_section_header)
            row += 1

            # Data rows
            section_net = 0.0
            section_tax_amt = 0.0

            for tax in section_taxes:
                net_amount = float(tax.get("net_amount", 0.0))
                tax_amount = float(tax.get("tax_amount", 0.0))
                tax_rate = float(tax.get("tax_rate", 0.0))
                section_net += net_amount
                section_tax_amt += tax_amount

                sheet.write(row, 0, tax.get("tax_name") or "", fmt_normal)
                sheet.write(row, 1, tax.get("tax_description") or "", fmt_normal)
                sheet.write(row, 2, tax_rate / 100.0 if tax_rate else 0.0, fmt_pct)
                sheet.write(row, 3, tax.get("tax_type") or "", fmt_normal)
                sheet.write(row, 4, net_amount, fmt_money)
                sheet.write(row, 5, tax_amount, fmt_money)
                row += 1

            # Subtotal row
            subtotal_label = f"Total {type_label}"
            sheet.write(row, 0, "", fmt_subtotal)
            sheet.write(row, 1, subtotal_label, fmt_subtotal)
            sheet.write(row, 2, "", fmt_subtotal)
            sheet.write(row, 3, "", fmt_subtotal)
            sheet.write(row, 4, section_net, fmt_subtotal_money)
            sheet.write(row, 5, section_tax_amt, fmt_subtotal_money)
            row += 1
            row += 1  # blank separator row

        # ── Grand total row ─────────────────────────────────────────
        sheet.write(row, 0, "", fmt_grand_total)
        sheet.write(row, 1, "GRAND TOTAL", fmt_grand_total)
        sheet.write(row, 2, "", fmt_grand_total)
        sheet.write(row, 3, "", fmt_grand_total)
        sheet.write(row, 4, total_net, fmt_grand_total_money)
        sheet.write(row, 5, total_tax, fmt_grand_total_money)