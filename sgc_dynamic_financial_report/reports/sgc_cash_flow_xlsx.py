# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcCashFlowXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Cash Flow Statement report."""

    _name = "report.sgc_dynamic_financial_report.sgc_cash_flow_xlsx"
    _description = "SGC Cash Flow XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Cash_Flow"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        activities = report_data.get("activities", {})
        activity_totals = report_data.get("totals", {})
        net_cash = float(report_data.get("net_cash", 0.0))

        formats = self._sgc_xlsx_build_formats(workbook)
        sheet = workbook.add_worksheet("Cash Flow")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="portrait")

        sheet.set_column("A:A", 18)   # Code
        sheet.set_column("B:B", 50)   # Description
        sheet.set_column("C:C", 20)   # Amount

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Cash Flow Statement",
            formats, column_count=3,
        )

        col_headers = ["Code", "Description", "Amount"]
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet, header_row=header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet, header_row, header_row, len(col_headers) - 1,
        )

        row = header_row + 1
        activity_order = [
            "Operating Activities",
            "Investing Activities",
            "Financing Activities",
        ]

        for activity_name in activity_order:
            lines = activities.get(activity_name, [])

            sheet.write(row, 0, activity_name.upper(), formats["section_header"])
            sheet.write(row, 1, "", formats["section_header"])
            sheet.write(row, 2, "", formats["section_header"])
            row += 1

            for line in lines:
                amount = float(line.get("amount") or 0.0)
                zebra = (row - header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet.write(row, 0, line.get("code") or "", fmt_text)
                sheet.write(row, 1, line.get("name") or "", fmt_text)
                sheet.write(row, 2, amount, fmt_money)
                row += 1

            activity_total = float(activity_totals.get(activity_name, 0.0))
            net_label = f"Net {activity_name}"
            sheet.write(row, 0, "", formats["subtotal"])
            sheet.write(row, 1, net_label, formats["subtotal"])
            sheet.write(row, 2, activity_total, formats["subtotal_money"])
            row += 1
            row += 1  # blank separator row

        sheet.write(row, 0, "", formats["grand_total"])
        sheet.write(row, 1, "NET CHANGE IN CASH", formats["grand_total"])
        sheet.write(row, 2, net_cash, formats["grand_total_money"])
        sheet.set_row(row, 22)
        row += 2

        self._sgc_xlsx_write_footer_block(sheet, formats, row, 3)