# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcPartnerLedgerXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Partner Ledger report."""

    _name = "report.sgc_dynamic_financial_report.sgc_partner_ledger_xlsx"
    _description = "SGC Partner Ledger XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    def _get_report_name(self):
        return "SGC_Partner_Ledger"

    def generate_xlsx_report(self, workbook, data, wizard):
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        partner_balances = report_data.get("partner_balances", [])
        partner_lines = report_data.get("partner_lines", {})

        formats = self._sgc_xlsx_build_formats(workbook)

        sheet_summary = workbook.add_worksheet("Partner Summary")
        self._sgc_xlsx_apply_page_setup(sheet_summary, orientation="landscape")
        sheet_summary.set_column("A:A", 40)
        sheet_summary.set_column("B:E", 18)

        sum_header_row = self._sgc_xlsx_write_header_block(
            sheet_summary, workbook, wizard, "Partner Ledger",
            formats, column_count=5,
        )

        summary_headers = ["Partner", "Ref", "Debit", "Credit", "Balance"]
        for col_idx, header in enumerate(summary_headers):
            sheet_summary.write(sum_header_row, col_idx, header, formats["col_header"])
        sheet_summary.set_row(sum_header_row, 26)

        self._sgc_xlsx_apply_freeze(sheet_summary, header_row=sum_header_row)
        self._sgc_xlsx_apply_autofilter(
            sheet_summary, sum_header_row, sum_header_row, len(summary_headers) - 1,
        )

        row = sum_header_row + 1
        grand_debit = 0.0
        grand_credit = 0.0
        grand_balance = 0.0

        for partner in partner_balances:
            debit = float(partner.get("debit") or 0.0)
            credit = float(partner.get("credit") or 0.0)
            balance = float(partner.get("balance") or 0.0)

            grand_debit += debit
            grand_credit += credit
            grand_balance += balance
            zebra = (row - sum_header_row) % 2 == 0
            fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
            fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

            sheet_summary.write(row, 0, partner.get("partner_name") or "", fmt_text)
            sheet_summary.write(row, 1, partner.get("partner_ref") or "", fmt_text)
            sheet_summary.write(row, 2, debit, fmt_money)
            sheet_summary.write(row, 3, credit, fmt_money)
            sheet_summary.write(row, 4, balance, fmt_money)
            row += 1

        sheet_summary.write(row, 0, "", formats["grand_total"])
        sheet_summary.write(row, 1, "TOTAL", formats["grand_total"])
        sheet_summary.write(row, 2, grand_debit, formats["grand_total_money"])
        sheet_summary.write(row, 3, grand_credit, formats["grand_total_money"])
        sheet_summary.write(row, 4, grand_balance, formats["grand_total_money"])
        sheet_summary.set_row(row, 22)
        row += 2
        self._sgc_xlsx_write_footer_block(sheet_summary, formats, row, 5)

        sheet_details = workbook.add_worksheet("Transaction Details")
        self._sgc_xlsx_apply_page_setup(sheet_details, orientation="landscape")
        sheet_details.set_column("A:A", 14)
        sheet_details.set_column("B:B", 16)
        sheet_details.set_column("C:C", 35)
        sheet_details.set_column("D:D", 18)
        sheet_details.set_column("E:F", 18)

        det_header_row = self._sgc_xlsx_write_header_block(
            sheet_details, workbook, wizard, "Partner Ledger",
            formats, column_count=6,
        )

        detail_headers = [
            "Date", "Journal Entry", "Description",
            "Account", "Debit", "Credit",
        ]

        sorted_partner_ids = sorted(
            partner_lines.keys(),
            key=lambda pid: (partner_lines[pid].get("partner_name") or "").lower(),
        )

        row = det_header_row + 1
        for idx, partner_id in enumerate(sorted_partner_ids):
            partner_data = partner_lines[partner_id]
            partner_name = partner_data.get("partner_name") or ""
            partner_ref = partner_data.get("partner_ref") or ""
            p_lines = partner_data.get("lines", [])
            p_total_debit = float(partner_data.get("total_debit") or 0.0)
            p_total_credit = float(partner_data.get("total_credit") or 0.0)

            heading_text = partner_name
            if partner_ref:
                heading_text = f"{partner_name} ({partner_ref})"
            sheet_details.merge_range(
                row, 0, row, 5, heading_text, formats["section_header"],
            )
            sheet_details.set_row(row, 22)
            row += 1

            for col_idx, header in enumerate(detail_headers):
                sheet_details.write(row, col_idx, header, formats["col_header"])
            row += 1

            for line in p_lines:
                debit = float(line.get("debit") or 0.0)
                credit = float(line.get("credit") or 0.0)
                zebra = (row - det_header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_date = self._sgc_xlsx_zebra_format(formats, zebra, date=True)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet_details.write(row, 0, line.get("date") or "", fmt_date)
                sheet_details.write(row, 1, line.get("move_name") or "", fmt_text)
                sheet_details.write(row, 2, line.get("entry_name") or "", fmt_text)
                sheet_details.write(row, 3, line.get("account_code") or "", fmt_text)
                sheet_details.write(row, 4, debit, fmt_money)
                sheet_details.write(row, 5, credit, fmt_money)
                row += 1

            sheet_details.write(row, 0, "", formats["subtotal"])
            sheet_details.write(row, 1, "", formats["subtotal"])
            sheet_details.write(row, 2, f"Total {partner_name}", formats["subtotal"])
            sheet_details.write(row, 3, "", formats["subtotal"])
            sheet_details.write(row, 4, p_total_debit, formats["subtotal_money"])
            sheet_details.write(row, 5, p_total_credit, formats["subtotal_money"])
            row += 1

            if idx < len(sorted_partner_ids) - 1:
                row += 2

        row += 1
        self._sgc_xlsx_write_footer_block(sheet_details, formats, row, 6)