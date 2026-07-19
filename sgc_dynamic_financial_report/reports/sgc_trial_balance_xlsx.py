# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcTrialBalanceXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Trial Balance report."""

    _name = "report.sgc_dynamic_financial_report.sgc_trial_balance_xlsx"
    _description = "SGC Trial Balance XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Trial_Balance"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Trial Balance Excel file.

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
        sheet = workbook.add_worksheet("Trial Balance")

        # Column widths: A=Code, B=Name, C=Type, D=Debit, E=Credit, F=Balance
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
        sheet.write(row, 0, "Trial Balance", fmt_title)
        row += 1
        sheet.write(row, 0, date_range, fmt_date)
        row += 2  # blank row at row 3

        # ── Column headers (row 4) ──────────────────────────────────
        col_headers = [
            "Account Code",
            "Account Name",
            "Account Type",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Data rows ───────────────────────────────────────────────
        for account in rows:
            debit = float(account.get("debit") or 0.0)
            credit = float(account.get("credit") or 0.0)
            balance = float(account.get("balance") or 0.0)

            sheet.write(row, 0, account.get("code") or "", fmt_normal)
            sheet.write(row, 1, account.get("name") or "", fmt_normal)
            sheet.write(row, 2, account.get("account_type") or "", fmt_normal)
            sheet.write(row, 3, debit, fmt_money)
            sheet.write(row, 4, credit, fmt_money)
            sheet.write(row, 5, balance, fmt_money)
            row += 1

        # ── Totals row ──────────────────────────────────────────────
        total_debit = float(totals.get("debit", 0.0))
        total_credit = float(totals.get("credit", 0.0))
        total_balance = float(totals.get("balance", 0.0))

        sheet.write(row, 0, "", fmt_total)
        sheet.write(row, 1, "TOTAL", fmt_total)
        sheet.write(row, 2, "", fmt_total)
        sheet.write(row, 3, total_debit, fmt_total_money)
        sheet.write(row, 4, total_credit, fmt_total_money)
        sheet.write(row, 5, total_balance, fmt_total_money)