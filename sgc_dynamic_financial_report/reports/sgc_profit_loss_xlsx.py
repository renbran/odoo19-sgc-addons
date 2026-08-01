# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcProfitLossXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Profit & Loss report."""

    _name = "report.sgc_dynamic_financial_report.sgc_profit_loss_xlsx"
    _description = "SGC Profit & Loss XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Profit_Loss"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        rows = report_data.get("rows", [])
        totals = report_data.get("totals", {})
        net_income = float(report_data.get("net_income", 0.0))

        formats = self._sgc_xlsx_build_formats(workbook)
        sheet = workbook.add_worksheet("Profit & Loss")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="portrait")

        sheet.set_column("A:A", 18)   # Account Code
        sheet.set_column("B:B", 45)   # Account Name
        sheet.set_column("C:C", 18)   # Debit
        sheet.set_column("D:D", 18)   # Credit
        sheet.set_column("E:E", 18)   # Balance

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Profit & Loss Statement",
            formats, column_count=5,
        )

        col_headers = [
            "Account Code", "Account Name", "Debit", "Credit", "Balance",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet, header_row=header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet, header_row, header_row, len(col_headers) - 1,
        )

        row = header_row + 1
        section_order = ["revenue", "expenses"]
        section_labels = {
            "revenue": "REVENUE",
            "expenses": "EXPENSES",
        }

        for section_key in section_order:
            label = section_labels.get(section_key, section_key.title())
            section_rows = [
                r for r in rows if r.get("financial_section") == section_key
            ]

            sheet.write(row, 0, label, formats["section_header"])
            sheet.write(row, 1, "", formats["section_header"])
            sheet.write(row, 2, "", formats["section_header"])
            sheet.write(row, 3, "", formats["section_header"])
            sheet.write(row, 4, "", formats["section_header"])
            row += 1

            for account in section_rows:
                debit = float(account.get("debit") or 0.0)
                credit = float(account.get("credit") or 0.0)
                balance = float(account.get("balance") or 0.0)
                zebra = (row - header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet.write(row, 0, account.get("code") or "", fmt_text)
                sheet.write(row, 1, account.get("name") or "", fmt_text)
                sheet.write(row, 2, debit, fmt_money)
                sheet.write(row, 3, credit, fmt_money)
                sheet.write(row, 4, balance, fmt_money)
                row += 1

            engine_section_total = float(totals.get(section_key, 0.0))
            subtotal_label = f"Total {label}"
            sheet.write(row, 0, "", formats["subtotal"])
            sheet.write(row, 1, subtotal_label, formats["subtotal"])
            sheet.write(row, 2, "", formats["subtotal_money"])
            sheet.write(row, 3, "", formats["subtotal_money"])
            sheet.write(row, 4, engine_section_total, formats["subtotal_money"])
            row += 1
            row += 1  # blank separator row

        is_loss = net_income < 0
        net_label = "NET LOSS" if is_loss else "NET INCOME"

        sheet.write(row, 0, "", formats["grand_total"])
        sheet.write(row, 1, net_label, formats["grand_total"])
        sheet.write(row, 2, "", formats["grand_total_money"])
        sheet.write(row, 3, "", formats["grand_total_money"])
        sheet.write(row, 4, net_income, formats["grand_total_money"])
        sheet.set_row(row, 22)
        row += 2

        self._sgc_xlsx_write_footer_block(sheet, formats, row, 5)