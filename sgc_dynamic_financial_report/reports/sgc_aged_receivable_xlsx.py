# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcAgedReceivableXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Aged Receivable report."""

    _name = "report.sgc_dynamic_financial_report.sgc_aged_receivable_xlsx"
    _description = "SGC Aged Receivable XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Aged_Receivable"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        rows = report_data.get("rows", [])
        buckets = report_data.get("buckets", [])
        totals = report_data.get("totals", {})

        formats = self._sgc_xlsx_build_formats(workbook)
        sheet = workbook.add_worksheet("Aged Receivable")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="landscape")

        num_buckets = len(buckets)
        total_col = 3 + num_buckets
        total_col_count = total_col + 1

        sheet.set_column("A:A", 35)
        sheet.set_column("B:B", 18)
        sheet.set_column("C:C", 14)
        for i in range(num_buckets):
            col_letter = self._sgc_xlsx_col_letter(3 + i)
            sheet.set_column(f"{col_letter}:{col_letter}", 16)
        total_col_letter = self._sgc_xlsx_col_letter(total_col)
        sheet.set_column(f"{total_col_letter}:{total_col_letter}", 18)

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Aged Receivable Report",
            formats, column_count=total_col_count,
        )

        col_headers = ["Partner", "Ref", "# Invoices"]
        for bucket in buckets:
            col_headers.append(bucket.get("label", ""))
        col_headers.append("Total Balance")
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet, header_row=header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet, header_row, header_row, len(col_headers) - 1,
        )

        row = header_row + 1
        for partner_row in rows:
            zebra = (row - header_row) % 2 == 0
            fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
            fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

            sheet.write(row, 0, partner_row.get("partner_name") or "", fmt_text)
            sheet.write(row, 1, partner_row.get("partner_ref") or "", fmt_text)
            sheet.write(row, 2, partner_row.get("invoice_count", 0), fmt_text)

            for b_idx, bucket in enumerate(buckets):
                label = bucket.get("label", "")
                value = float(partner_row.get(label, 0.0))
                sheet.write(row, 3 + b_idx, value, fmt_money)

            total_balance = float(partner_row.get("total_balance", 0.0))
            sheet.write(row, total_col, total_balance, fmt_money)
            row += 1

        zebra = (row - header_row) % 2 == 0
        fmt_total_text = self._sgc_xlsx_zebra_format(formats, zebra, money=True)
        sheet.write(row, 0, "", fmt_total_text)
        sheet.write(row, 1, "", fmt_total_text)
        sheet.write(row, 2, "", fmt_total_text)
        for b_idx, bucket in enumerate(buckets):
            label = bucket.get("label", "")
            value = float(totals.get(label, 0.0))
            sheet.write(row, 3 + b_idx, value, formats["grand_total_money"])
        grand_total = float(totals.get("total_balance", 0.0))
        sheet.write(row, total_col, grand_total, formats["grand_total_money"])
        sheet.set_row(row, 22)
        row += 2

        self._sgc_xlsx_write_footer_block(sheet, formats, row, total_col_count)