# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcCashFlowXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Cash Flow Statement report."""

    _name = "report.sgc_dynamic_financial_report.sgc_cash_flow_xlsx"
    _description = "SGC Cash Flow XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Cash_Flow"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Cash Flow Statement Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        # ── Fetch data from the report engine ───────────────────────
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        activities = report_data.get("activities", {})
        activity_totals = report_data.get("totals", {})
        net_cash = float(report_data.get("net_cash", 0.0))

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
            "size": 12,
            "top": 2,
            "bottom": 2,
            "valign": "vcenter",
        })
        fmt_grand_total_money = workbook.add_format({
            "bold": True,
            "size": 12,
            "top": 2,
            "bottom": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })

        # ── Sheet setup ─────────────────────────────────────────────
        sheet = workbook.add_worksheet("Cash Flow")

        # Column widths: A=Code, B=Description, C=Amount
        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 50)
        sheet.set_column("C:C", 20)

        # ── Report header ───────────────────────────────────────────
        row = 0
        sheet.write(row, 0, wizard.company_id.name or "", fmt_title)
        row += 1
        sheet.write(row, 0, "Cash Flow Statement", fmt_title)
        row += 1
        sheet.write(row, 0, date_range, fmt_date)
        row += 2  # blank row at row 3

        # ── Column headers (row 4) ──────────────────────────────────
        col_headers = ["Code", "Description", "Amount"]
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Activity sections ───────────────────────────────────────
        activity_order = [
            "Operating Activities",
            "Investing Activities",
            "Financing Activities",
        ]

        for activity_name in activity_order:
            lines = activities.get(activity_name, [])

            # Section header row
            sheet.write(row, 0, activity_name.upper(), fmt_section_header)
            sheet.write(row, 1, "", fmt_section_header)
            sheet.write(row, 2, "", fmt_section_header)
            row += 1

            # Data rows for this activity
            for line in lines:
                amount = float(line.get("amount") or 0.0)

                sheet.write(row, 0, line.get("code") or "", fmt_normal)
                sheet.write(row, 1, line.get("name") or "", fmt_normal)
                sheet.write(row, 2, amount, fmt_money)
                row += 1

            # Net amount row for this activity
            activity_total = float(activity_totals.get(activity_name, 0.0))
            net_label = f"Net {activity_name}"
            sheet.write(row, 0, "", fmt_subtotal)
            sheet.write(row, 1, net_label, fmt_subtotal)
            sheet.write(row, 2, activity_total, fmt_subtotal_money)
            row += 1
            row += 1  # blank separator row

        # ── Grand total: NET CHANGE IN CASH ─────────────────────────
        sheet.write(row, 0, "", fmt_grand_total)
        sheet.write(row, 1, "NET CHANGE IN CASH", fmt_grand_total)
        sheet.write(row, 2, net_cash, fmt_grand_total_money)