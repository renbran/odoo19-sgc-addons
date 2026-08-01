# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from collections import OrderedDict

from odoo import models


class SgcTaxReportXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Tax Report."""

    _name = "report.sgc_dynamic_financial_report.sgc_tax_report_xlsx"
    _description = "SGC Tax Report XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Tax_Report"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        taxes = report_data.get("taxes", [])
        total_net = float(report_data.get("total_net", 0.0))
        total_tax = float(report_data.get("total_tax", 0.0))

        formats = self._sgc_xlsx_build_formats(workbook)
        sheet = workbook.add_worksheet("Tax Report")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="landscape")

        sheet.set_column("A:A", 30)
        sheet.set_column("B:B", 40)
        sheet.set_column("C:C", 12)
        sheet.set_column("D:D", 25)
        sheet.set_column("E:F", 18)

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Tax Report", formats, column_count=6,
        )

        col_headers = [
            "Tax Name", "Description", "Rate %", "Type",
            "Net Amount", "Tax Amount",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet, header_row=header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet, header_row, header_row, len(col_headers) - 1,
        )

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

        row = header_row + 1
        for type_key, type_label in type_labels.items():
            section_taxes = grouped.get(type_key, [])
            if not section_taxes:
                continue

            sheet.write(row, 0, type_label, formats["section_header"])
            sheet.write(row, 1, "", formats["section_header"])
            sheet.write(row, 2, "", formats["section_header"])
            sheet.write(row, 3, "", formats["section_header"])
            sheet.write(row, 4, "", formats["section_header"])
            sheet.write(row, 5, "", formats["section_header"])
            sheet.set_row(row, 22)
            row += 1

            section_net = 0.0
            section_tax_amt = 0.0

            for tax in section_taxes:
                net_amount = float(tax.get("net_amount", 0.0))
                tax_amount = float(tax.get("tax_amount", 0.0))
                tax_rate = float(tax.get("tax_rate", 0.0))
                section_net += net_amount
                section_tax_amt += tax_amount
                zebra = (row - header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet.write(row, 0, tax.get("tax_name") or "", fmt_text)
                sheet.write(row, 1, tax.get("tax_description") or "", fmt_text)
                sheet.write(row, 2, tax_rate / 100.0 if tax_rate else 0.0, formats["pct"])
                sheet.write(row, 3, tax.get("tax_type") or "", fmt_text)
                sheet.write(row, 4, net_amount, fmt_money)
                sheet.write(row, 5, tax_amount, fmt_money)
                row += 1

            subtotal_label = f"Total {type_label}"
            sheet.write(row, 0, "", formats["subtotal"])
            sheet.write(row, 1, subtotal_label, formats["subtotal"])
            sheet.write(row, 2, "", formats["subtotal"])
            sheet.write(row, 3, "", formats["subtotal"])
            sheet.write(row, 4, section_net, formats["subtotal_money"])
            sheet.write(row, 5, section_tax_amt, formats["subtotal_money"])
            row += 1
            row += 1  # blank separator row

        sheet.write(row, 0, "", formats["grand_total"])
        sheet.write(row, 1, "GRAND TOTAL", formats["grand_total"])
        sheet.write(row, 2, "", formats["grand_total"])
        sheet.write(row, 3, "", formats["grand_total"])
        sheet.write(row, 4, total_net, formats["grand_total_money"])
        sheet.write(row, 5, total_tax, formats["grand_total_money"])
        sheet.set_row(row, 22)
        row += 2

        self._sgc_xlsx_write_footer_block(sheet, formats, row, 6)