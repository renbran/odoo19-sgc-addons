# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcTrialBalanceXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Trial Balance report."""

    _name = "report.sgc_dynamic_financial_report.sgc_trial_balance_xlsx"
    _description = "SGC Trial Balance XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Trial_Balance"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        rows = report_data.get("rows", [])
        totals = report_data.get("totals", {})

        formats = self._sgc_xlsx_build_formats(workbook)
        sheet = workbook.add_worksheet("Trial Balance")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="landscape")

        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 45)
        sheet.set_column("C:C", 22)
        sheet.set_column("D:D", 18)
        sheet.set_column("E:E", 18)
        sheet.set_column("F:F", 18)

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Trial Balance", formats, column_count=6,
        )

        col_headers = [
            "Account Code",
            "Account Name",
            "Account Type",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet, header_row=header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet, header_row, header_row, len(col_headers) - 1,
        )

        row = header_row + 1
        for account in rows:
            debit = float(account.get("debit") or 0.0)
            credit = float(account.get("credit") or 0.0)
            balance = float(account.get("balance") or 0.0)
            zebra = (row - header_row) % 2 == 0
            fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
            fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

            sheet.write(row, 0, account.get("code") or "", fmt_text)
            sheet.write(row, 1, account.get("name") or "", fmt_text)
            sheet.write(row, 2, account.get("account_type") or "", fmt_text)
            sheet.write(row, 3, debit, fmt_money)
            sheet.write(row, 4, credit, fmt_money)
            sheet.write(row, 5, balance, fmt_money)
            row += 1

        total_debit = float(totals.get("debit", 0.0))
        total_credit = float(totals.get("credit", 0.0))
        total_balance = float(totals.get("balance", 0.0))

        sheet.write(row, 0, "", formats["grand_total"])
        sheet.write(row, 1, "TOTAL", formats["grand_total"])
        sheet.write(row, 2, "", formats["grand_total"])
        sheet.write(row, 3, total_debit, formats["grand_total_money"])
        sheet.write(row, 4, total_credit, formats["grand_total_money"])
        sheet.write(row, 5, total_balance, formats["grand_total_money"])
        sheet.set_row(row, 22)
        row += 2

        self._sgc_xlsx_write_footer_block(sheet, formats, row, 6)