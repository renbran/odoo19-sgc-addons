# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcBalanceSheetXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Balance Sheet report."""

    _name = "report.sgc_dynamic_financial_report.sgc_balance_sheet_xlsx"
    _description = "SGC Balance Sheet XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Balance_Sheet"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Balance Sheet Excel file.

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
        sheet = workbook.add_worksheet("Balance Sheet")

        # Column widths: A=Code, B=Name, C=Section, D=Debit, E=Credit, F=Balance
        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 45)
        sheet.set_column("C:C", 22)
        sheet.set_column("D:D", 18)
        sheet.set_column("E:E", 18)
        sheet.set_column("F:F", 18)

        # ── Report header ───────────────────────────────────────────
        row = 0
        sheet.write(row, 0, wizard.company_id.name or "", fmt_title)
        row += 1
        sheet.write(row, 0, "Balance Sheet", fmt_title)
        row += 1
        sheet.write(row, 0, date_range, fmt_date)
        row += 2  # blank row at row 3

        # ── Column headers (row 4) ──────────────────────────────────
        col_headers = [
            "Account Code",
            "Account Name",
            "Financial Section",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Group rows by financial_section and write sections ──────
        section_order = ["assets", "liabilities", "equity"]
        section_labels = {
            "assets": "ASSETS",
            "liabilities": "LIABILITIES",
            "equity": "EQUITY",
        }
        section_running = {
            "assets": 0.0,
            "liabilities": 0.0,
            "equity": 0.0,
        }

        for section_key in section_order:
            label = section_labels.get(section_key, section_key.title())
            section_rows = [
                r for r in rows if r.get("financial_section") == section_key
            ]

            # Section header row
            sheet.write(row, 0, label, fmt_section_header)
            sheet.write(row, 1, "", fmt_section_header)
            sheet.write(row, 2, "", fmt_section_header)
            sheet.write(row, 3, "", fmt_section_header)
            sheet.write(row, 4, "", fmt_section_header)
            sheet.write(row, 5, "", fmt_section_header)
            row += 1

            # Data rows for this section
            section_total = 0.0
            for account in section_rows:
                balance = float(account.get("balance") or 0.0)
                debit = float(account.get("debit") or 0.0)
                credit = float(account.get("credit") or 0.0)
                section_total += balance

                sheet.write(row, 0, account.get("code") or "", fmt_normal)
                sheet.write(row, 1, account.get("name") or "", fmt_normal)
                sheet.write(row, 2, account.get("financial_section") or "", fmt_normal)
                sheet.write(row, 3, debit, fmt_money)
                sheet.write(row, 4, credit, fmt_money)
                sheet.write(row, 5, balance, fmt_money)
                row += 1

            section_running[section_key] = section_total

            # Subtotal row (use engine total if available, otherwise computed)
            engine_section_total = float(
                totals.get(section_key, section_total)
            )
            subtotal_label = f"Total {label}"
            sheet.write(row, 0, "", fmt_subtotal)
            sheet.write(row, 1, subtotal_label, fmt_subtotal)
            sheet.write(row, 2, "", fmt_subtotal)
            sheet.write(row, 3, "", fmt_subtotal_money)
            sheet.write(row, 4, "", fmt_subtotal_money)
            sheet.write(row, 5, engine_section_total, fmt_subtotal_money)
            row += 1
            row += 1  # blank separator row

        # ── Grand totals ────────────────────────────────────────────
        total_assets = float(totals.get("assets", 0.0))
        total_liabilities_equity = float(totals.get("liabilities_equity", 0.0))

        sheet.write(row, 0, "", fmt_grand_total)
        sheet.write(row, 1, "TOTAL ASSETS", fmt_grand_total)
        sheet.write(row, 2, "", fmt_grand_total)
        sheet.write(row, 3, "", fmt_grand_total_money)
        sheet.write(row, 4, "", fmt_grand_total_money)
        sheet.write(row, 5, total_assets, fmt_grand_total_money)
        row += 1

        sheet.write(row, 0, "", fmt_grand_total)
        sheet.write(row, 1, "TOTAL LIABILITIES + EQUITY", fmt_grand_total)
        sheet.write(row, 2, "", fmt_grand_total)
        sheet.write(row, 3, "", fmt_grand_total_money)
        sheet.write(row, 4, "", fmt_grand_total_money)
        sheet.write(row, 5, total_liabilities_equity, fmt_grand_total_money)