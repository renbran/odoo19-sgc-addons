# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcBalanceSheetXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Balance Sheet report.

    The workbook deliberately carries the same figures in two different
    shapes, because the two audiences want opposite things:

    * "Balance Sheet"  - presentation/print sheet. Only the columns a
      reader actually needs (code, name, balance), fitted to one page
      wide with the column header repeated on every printed page. This
      is the sheet you hand to someone.
    * "Working Data"   - reconciliation sheet. Every column including
      Financial Section / Debit / Credit, plus freeze panes and an
      autofilter, so it can be sorted, filtered and tied out. This is
      the sheet you work in.
    """

    _name = "report.sgc_dynamic_financial_report.sgc_balance_sheet_xlsx"
    _description = "SGC Balance Sheet XLSX Report"
    _inherit = [
        "report.report_xlsx.abstract",
        "report.sgc_dynamic_financial_report.xlsx_mixin",
    ]

    SECTION_ORDER = ["assets", "liabilities", "equity"]
    SECTION_LABELS = {
        "assets": "ASSETS",
        "liabilities": "LIABILITIES",
        "equity": "EQUITY",
    }

    def _get_report_name(self):
        return "SGC_Balance_Sheet"

    # ── helpers ────────────────────────────────────────────────────────

    def _sgc_bs_section_rows(self, rows, section_key):
        return [r for r in rows if r.get("financial_section") == section_key]

    def _sgc_bs_section_total(self, section_rows):
        """Subtotal for one section.

        ``totals`` only carries combined "assets" / "liabilities_equity"
        keys (see _build_balance_sheet's return shape) - there is no
        separate "liabilities" or "equity" key, so summing this section's
        own rows is the only correct way to get its subtotal.
        """
        return sum(float(r.get("natural_balance") or 0.0) for r in section_rows)

    # ── entry point ────────────────────────────────────────────────────

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Balance Sheet Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        rows = report_data.get("rows", [])
        totals = report_data.get("totals", {})

        formats = self._sgc_xlsx_build_formats(workbook)

        self._sgc_bs_write_presentation_sheet(workbook, wizard, formats, rows, totals)
        self._sgc_bs_write_working_sheet(workbook, wizard, formats, rows, totals)

    # ── sheet 1: presentation / print ──────────────────────────────────

    def _sgc_bs_write_presentation_sheet(self, workbook, wizard, formats, rows, totals):
        """Clean, print-ready sheet: code, name, balance only.

        Debit/Credit are intentionally omitted here - on a balance sheet
        they are zero for almost every line, so they add two dead columns
        and push the report onto a second printed page without telling
        the reader anything. They remain available on the Working Data
        sheet for anyone reconciling.
        """
        col_count = 3
        sheet = workbook.add_worksheet("Balance Sheet")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="portrait")

        # Print behaviour: one page wide, as many pages tall as needed,
        # with the column header repeated at the top of each page.
        sheet.fit_to_pages(1, 0)
        sheet.hide_gridlines(2)

        sheet.set_column("A:A", 16)   # Account Code
        sheet.set_column("B:B", 56)   # Account Name
        sheet.set_column("C:C", 22)   # Balance

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Balance Sheet", formats, column_count=col_count,
        )

        col_headers = ["Account Code", "Account Name", "Balance"]
        for col_idx, header in enumerate(col_headers):
            sheet.write(header_row, col_idx, header, formats["col_header"])
        sheet.set_row(header_row, 26)
        sheet.repeat_rows(header_row)

        row = header_row + 1
        for section_key in self.SECTION_ORDER:
            label = self.SECTION_LABELS.get(section_key, section_key.title())
            section_rows = self._sgc_bs_section_rows(rows, section_key)

            for col_idx in range(col_count):
                sheet.write(row, col_idx, label if col_idx == 0 else "",
                            formats["section_header"])
            row += 1

            for account in section_rows:
                zebra = (row - header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet.write(row, 0, account.get("code") or "", fmt_text)
                sheet.write(row, 1, account.get("name") or "", fmt_text)
                sheet.write(row, 2, float(account.get("balance") or 0.0), fmt_money)
                row += 1

            sheet.write(row, 0, "", formats["subtotal"])
            sheet.write(row, 1, f"Total {label}", formats["subtotal"])
            sheet.write(row, 2, self._sgc_bs_section_total(section_rows),
                        formats["subtotal_money"])
            row += 2  # subtotal + blank separator

        for caption, value in (
            ("TOTAL ASSETS", float(totals.get("assets", 0.0))),
            ("TOTAL LIABILITIES + EQUITY", float(totals.get("liabilities_equity", 0.0))),
        ):
            sheet.write(row, 0, "", formats["grand_total"])
            sheet.write(row, 1, caption, formats["grand_total"])
            sheet.write(row, 2, value, formats["grand_total_money"])
            sheet.set_row(row, 22)
            row += 1

        row += 1
        self._sgc_xlsx_write_footer_block(sheet, formats, row, col_count)

    # ── sheet 2: working / reconciliation ──────────────────────────────

    def _sgc_bs_write_working_sheet(self, workbook, wizard, formats, rows, totals):
        """Full-detail sheet for reconciling: every column, filterable."""
        col_count = 6
        sheet = workbook.add_worksheet("Working Data")
        self._sgc_xlsx_apply_page_setup(sheet, orientation="landscape")

        sheet.set_column("A:A", 18)   # Account Code
        sheet.set_column("B:B", 45)   # Account Name
        sheet.set_column("C:C", 22)   # Financial Section
        sheet.set_column("D:D", 18)   # Debit
        sheet.set_column("E:E", 18)   # Credit
        sheet.set_column("F:F", 18)   # Balance

        header_row = self._sgc_xlsx_write_header_block(
            sheet, workbook, wizard, "Balance Sheet - Working Data", formats,
            column_count=col_count,
        )

        col_headers = [
            "Account Code",
            "Account Name",
            "Financial Section",
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
        for section_key in self.SECTION_ORDER:
            label = self.SECTION_LABELS.get(section_key, section_key.title())
            section_rows = self._sgc_bs_section_rows(rows, section_key)

            for col_idx in range(col_count):
                sheet.write(row, col_idx, label if col_idx == 0 else "",
                            formats["section_header"])
            row += 1

            for account in section_rows:
                zebra = (row - header_row) % 2 == 0
                fmt_text = self._sgc_xlsx_zebra_format(formats, zebra)
                fmt_money = self._sgc_xlsx_zebra_format(formats, zebra, money=True)

                sheet.write(row, 0, account.get("code") or "", fmt_text)
                sheet.write(row, 1, account.get("name") or "", fmt_text)
                sheet.write(row, 2, account.get("financial_section") or "", fmt_text)
                sheet.write(row, 3, float(account.get("debit") or 0.0), fmt_money)
                sheet.write(row, 4, float(account.get("credit") or 0.0), fmt_money)
                sheet.write(row, 5, float(account.get("balance") or 0.0), fmt_money)
                row += 1

            sheet.write(row, 0, "", formats["subtotal"])
            sheet.write(row, 1, f"Total {label}", formats["subtotal"])
            sheet.write(row, 2, "", formats["subtotal"])
            sheet.write(row, 3, "", formats["subtotal_money"])
            sheet.write(row, 4, "", formats["subtotal_money"])
            sheet.write(row, 5, self._sgc_bs_section_total(section_rows),
                        formats["subtotal_money"])
            row += 2  # subtotal + blank separator

        for caption, value in (
            ("TOTAL ASSETS", float(totals.get("assets", 0.0))),
            ("TOTAL LIABILITIES + EQUITY", float(totals.get("liabilities_equity", 0.0))),
        ):
            sheet.write(row, 0, "", formats["grand_total"])
            sheet.write(row, 1, caption, formats["grand_total"])
            sheet.write(row, 2, "", formats["grand_total"])
            sheet.write(row, 3, "", formats["grand_total_money"])
            sheet.write(row, 4, "", formats["grand_total_money"])
            sheet.write(row, 5, value, formats["grand_total_money"])
            sheet.set_row(row, 22)
            row += 1

        row += 1
        self._sgc_xlsx_write_footer_block(sheet, formats, row, col_count)
