# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcGeneralLedgerXlsx(models.AbstractModel):
    """XLSX renderer for the SGC General Ledger report."""

    _name = "report.sgc_dynamic_financial_report.sgc_general_ledger_xlsx"
    _description = "SGC General Ledger XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_General_Ledger"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        accounts = report_data.get("accounts", [])
        lines = report_data.get("lines", [])

        formats = self._sgc_xlsx_build_formats(workbook)

        sheet_summary = workbook.add_worksheet("Account Summary")
        self._sgc_xlsx_apply_page_setup(sheet_summary, orientation="landscape")
        sheet_summary.set_column("A:A", 18)
        sheet_summary.set_column("B:B", 45)
        sheet_summary.set_column("C:G", 18)

        sum_header_row = self._sgc_xlsx_write_header_block(
            sheet_summary, workbook, wizard, "General Ledger",
            formats, column_count=7,
        )

        summary_headers = [
            "Account Code", "Account Name",
            "Opening Balance", "Period Debit", "Period Credit",
            "Period Balance", "Final Balance",
        ]
        for col_idx, header in enumerate(summary_headers):
            sheet_summary.write(sum_header_row, col_idx, header, formats["col_header"])
        sheet_summary.set_row(sum_header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet_summary, header_row=sum_header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet_summary, sum_header_row, sum_header_row, len(summary_headers) - 1,
        )

        row = sum_header_row + 1
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
            zebra = (row - sum_header_row) % 2 == 0
            fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
            fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

            sheet_summary.write(row, 0, account.get("account_code") or "", fmt_text)
            sheet_summary.write(row, 1, account.get("account_name") or "", fmt_text)
            sheet_summary.write(row, 2, opening_balance, fmt_money)
            sheet_summary.write(row, 3, period_debit, fmt_money)
            sheet_summary.write(row, 4, period_credit, fmt_money)
            sheet_summary.write(row, 5, period_balance, fmt_money)
            sheet_summary.write(row, 6, final_balance, fmt_money)
            row += 1

        sheet_summary.write(row, 0, "", formats["grand_total"])
        sheet_summary.write(row, 1, "TOTAL", formats["grand_total"])
        sheet_summary.write(row, 2, sum_opening, formats["grand_total_money"])
        sheet_summary.write(row, 3, sum_period_debit, formats["grand_total_money"])
        sheet_summary.write(row, 4, sum_period_credit, formats["grand_total_money"])
        sheet_summary.write(row, 5, sum_period_bal, formats["grand_total_money"])
        sheet_summary.write(row, 6, sum_final, formats["grand_total_money"])
        sheet_summary.set_row(row, 22)
        row += 2
        self._sgc_xlsx_write_footer_block(sheet_summary, formats, row, 7)

        sheet_details = workbook.add_worksheet("Journal Details")
        self._sgc_xlsx_apply_page_setup(sheet_details, orientation="landscape")
        sheet_details.set_column("A:A", 14)
        sheet_details.set_column("B:B", 16)
        sheet_details.set_column("C:C", 35)
        sheet_details.set_column("D:D", 25)
        sheet_details.set_column("E:E", 18)
        sheet_details.set_column("F:H", 18)

        det_header_row = self._sgc_xlsx_write_header_block(
            sheet_details, workbook, wizard, "General Ledger",
            formats, column_count=8,
        )

        detail_headers = [
            "Date", "Journal Entry", "Description", "Partner",
            "Account", "Debit", "Credit", "Balance",
        ]
        for col_idx, header in enumerate(detail_headers):
            sheet_details.write(det_header_row, col_idx, header, formats["col_header"])
        sheet_details.set_row(det_header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet_details, header_row=det_header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet_details, det_header_row, det_header_row, len(detail_headers) - 1,
        )

        row = det_header_row + 1
        for line in lines:
            debit = float(line.get("debit") or 0.0)
            credit = float(line.get("credit") or 0.0)
            balance = float(line.get("balance") or 0.0)
            zebra = (row - det_header_row) % 2 == 0
            fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
            fmt_date = self._sgc_xlsx_zebra_format(formats, zebra, date=True)
            fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

            sheet_details.write(row, 0, line.get("date") or "", fmt_date)
            sheet_details.write(row, 1, line.get("move_name") or "", fmt_text)
            sheet_details.write(row, 2, line.get("entry_name") or "", fmt_text)
            sheet_details.write(row, 3, line.get("partner_name") or "", fmt_text)
            sheet_details.write(row, 4, line.get("account_code") or "", fmt_text)
            sheet_details.write(row, 5, debit, fmt_money)
            sheet_details.write(row, 6, credit, fmt_money)
            sheet_details.write(row, 7, balance, fmt_money)
            row += 1
        row += 1
        self._sgc_xlsx_write_footer_block(sheet_details, formats, row, 8)