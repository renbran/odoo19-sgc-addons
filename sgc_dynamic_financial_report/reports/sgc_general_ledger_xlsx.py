# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcGeneralLedgerXlsx(models.AbstractModel):
    """XLSX renderer for the SGC General Ledger report."""

    _name = "report.sgc_dynamic_financial_report.sgc_general_ledger_xlsx"
    _description = "SGC General Ledger XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_General_Ledger"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the General Ledger Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        # ── Fetch data from the report engine ───────────────────────
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        accounts = report_data.get("accounts", [])
        lines = report_data.get("lines", [])

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
        fmt_date_value = workbook.add_format({
            "size": 10,
            "num_format": "YYYY-MM-DD",
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

        # ── Shared header writing helper ────────────────────────────
        def _write_header(sheet):
            sheet.write(0, 0, wizard.company_id.name or "", fmt_title)
            sheet.write(1, 0, "General Ledger", fmt_title)
            sheet.write(2, 0, date_range, fmt_date)

        # ═══════════════════════════════════════════════════════════
        # Sheet 1 – Account Summary
        # ═══════════════════════════════════════════════════════════
        sheet_summary = workbook.add_worksheet("Account Summary")

        # Column widths
        sheet_summary.set_column("A:A", 18)   # Account Code
        sheet_summary.set_column("B:B", 45)   # Account Name
        sheet_summary.set_column("C:C", 18)   # Opening Balance
        sheet_summary.set_column("D:D", 18)   # Period Debit
        sheet_summary.set_column("E:E", 18)   # Period Credit
        sheet_summary.set_column("F:F", 18)   # Period Balance
        sheet_summary.set_column("G:G", 18)   # Final Balance

        _write_header(sheet_summary)
        row = 4

        summary_headers = [
            "Account Code",
            "Account Name",
            "Opening Balance",
            "Period Debit",
            "Period Credit",
            "Period Balance",
            "Final Balance",
        ]
        for col_idx, header in enumerate(summary_headers):
            sheet_summary.write(row, col_idx, header, fmt_col_header)
        row += 1

        sum_opening = 0.0
        sum_period_debit = 0.0
        sum_period_credit = 0.0
        sum_period_bal = 0.0
        sum_final = 0.0

        for account in accounts:
            opening_balance = float(account.get("opening_balance") or 0.0)
            period_debit = float(account.get("period_debit") or 0.0)
            period_credit = float(account.get("period_credit") or 0.0)
            period_balance = float(account.get("period_balance") or 0.0)
            final_balance = float(account.get("final_balance") or 0.0)

            sum_opening += opening_balance
            sum_period_debit += period_debit
            sum_period_credit += period_credit
            sum_period_bal += period_balance
            sum_final += final_balance

            sheet_summary.write(row, 0, account.get("account_code") or "", fmt_normal)
            sheet_summary.write(row, 1, account.get("account_name") or "", fmt_normal)
            sheet_summary.write(row, 2, opening_balance, fmt_money)
            sheet_summary.write(row, 3, period_debit, fmt_money)
            sheet_summary.write(row, 4, period_credit, fmt_money)
            sheet_summary.write(row, 5, period_balance, fmt_money)
            sheet_summary.write(row, 6, final_balance, fmt_money)
            row += 1

        # Totals row
        sheet_summary.write(row, 0, "", fmt_total)
        sheet_summary.write(row, 1, "TOTAL", fmt_total)
        sheet_summary.write(row, 2, sum_opening, fmt_total_money)
        sheet_summary.write(row, 3, sum_period_debit, fmt_total_money)
        sheet_summary.write(row, 4, sum_period_credit, fmt_total_money)
        sheet_summary.write(row, 5, sum_period_bal, fmt_total_money)
        sheet_summary.write(row, 6, sum_final, fmt_total_money)

        # ═══════════════════════════════════════════════════════════
        # Sheet 2 – Journal Details
        # ═══════════════════════════════════════════════════════════
        sheet_details = workbook.add_worksheet("Journal Details")

        # Column widths
        sheet_details.set_column("A:A", 14)   # Date
        sheet_details.set_column("B:B", 16)   # Journal Entry
        sheet_details.set_column("C:C", 35)   # Description
        sheet_details.set_column("D:D", 25)   # Partner
        sheet_details.set_column("E:E", 18)   # Account
        sheet_details.set_column("F:F", 18)   # Debit
        sheet_details.set_column("G:G", 18)   # Credit
        sheet_details.set_column("H:H", 18)   # Balance

        _write_header(sheet_details)
        row = 4

        detail_headers = [
            "Date",
            "Journal Entry",
            "Description",
            "Partner",
            "Account",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(detail_headers):
            sheet_details.write(row, col_idx, header, fmt_col_header)
        row += 1

        for line in lines:
            debit = float(line.get("debit") or 0.0)
            credit = float(line.get("credit") or 0.0)
            balance = float(line.get("balance") or 0.0)

            sheet_details.write(row, 0, line.get("date") or "", fmt_date_value)
            sheet_details.write(row, 1, line.get("move_name") or "", fmt_normal)
            sheet_details.write(row, 2, line.get("entry_name") or "", fmt_normal)
            sheet_details.write(row, 3, line.get("partner_name") or "", fmt_normal)
            sheet_details.write(row, 4, line.get("account_code") or "", fmt_normal)
            sheet_details.write(row, 5, debit, fmt_money)
            sheet_details.write(row, 6, credit, fmt_money)
            sheet_details.write(row, 7, balance, fmt_money)
            row += 1