# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcProfitLossXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Profit & Loss report."""

    _name = "report.sgc_dynamic_financial_report.sgc_profit_loss_xlsx"
    _description = "SGC Profit & Loss XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Profit_Loss"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Profit & Loss Excel file.

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
        net_income = float(report_data.get("net_income", 0.0))

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
        fmt_section_header = workbook.add_format({
            "bold": True,
            "size": 11,
            "bg_color": "#D9E2F3",
            "border": 1,
            "valign": "vcenter",
        })
        fmt_normal = workbook.add_format({
            "size": 10,
            "valign": "vcenter",
        })
        fmt_money = workbook.add_format({
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })
        fmt_subtotal = workbook.add_format({
            "bold": True,
            "size": 10,
            "top": 2,
            "valign": "vcenter",
        })
        fmt_subtotal_money = workbook.add_format({
            "bold": True,
            "size": 10,
            "top": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })
        fmt_net_income = workbook.add_format({
            "bold": True,
            "size": 12,
            "top": 2,
            "bottom": 2,
            "valign": "vcenter",
        })
        fmt_net_income_money = workbook.add_format({
            "bold": True,
            "size": 12,
            "top": 2,
            "bottom": 2,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })

        # ── Sheet setup ─────────────────────────────────────────────
        sheet = workbook.add_worksheet("Profit & Loss")

        # Column widths: A=Code, B=Name, C=Debit, D=Credit, E=Balance
        sheet.set_column("A:A", 18)
        sheet.set_column("B:B", 45)
        sheet.set_column("C:C", 18)
        sheet.set_column("D:D", 18)
        sheet.set_column("E:E", 18)

        # ── Report header ───────────────────────────────────────────
        row = 0
        sheet.write(row, 0, wizard.company_id.name or "", fmt_title)
        row += 1
        sheet.write(row, 0, "Profit & Loss Statement", fmt_title)
        row += 1
        sheet.write(row, 0, date_range, fmt_date)
        row += 2  # blank row at row 3

        # ── Column headers (row 4) ──────────────────────────────────
        col_headers = [
            "Account Code",
            "Account Name",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(col_headers):
            sheet.write(row, col_idx, header, fmt_col_header)
        row += 1

        # ── Group rows by financial_section and write sections ──────
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

            # Section header row
            sheet.write(row, 0, label, fmt_section_header)
            sheet.write(row, 1, "", fmt_section_header)
            sheet.write(row, 2, "", fmt_section_header)
            sheet.write(row, 3, "", fmt_section_header)
            sheet.write(row, 4, "", fmt_section_header)
            row += 1

            # Data rows for this section
            for account in section_rows:
                debit = float(account.get("debit") or 0.0)
                credit = float(account.get("credit") or 0.0)
                balance = float(account.get("balance") or 0.0)

                sheet.write(row, 0, account.get("code") or "", fmt_normal)
                sheet.write(row, 1, account.get("name") or "", fmt_normal)
                sheet.write(row, 2, debit, fmt_money)
                sheet.write(row, 3, credit, fmt_money)
                sheet.write(row, 4, balance, fmt_money)
                row += 1

            # Subtotal row
            engine_section_total = float(totals.get(section_key, 0.0))
            subtotal_label = f"Total {label}"
            sheet.write(row, 0, "", fmt_subtotal)
            sheet.write(row, 1, subtotal_label, fmt_subtotal)
            sheet.write(row, 2, "", fmt_subtotal_money)
            sheet.write(row, 3, "", fmt_subtotal_money)
            sheet.write(row, 4, engine_section_total, fmt_subtotal_money)
            row += 1
            row += 1  # blank separator row

        # ── Net Income / Net Loss row ───────────────────────────────
        is_loss = net_income < 0
        net_label = "NET LOSS" if is_loss else "NET INCOME"

        sheet.write(row, 0, "", fmt_net_income)
        sheet.write(row, 1, net_label, fmt_net_income)
        sheet.write(row, 2, "", fmt_net_income_money)
        sheet.write(row, 3, "", fmt_net_income_money)
        sheet.write(row, 4, net_income, fmt_net_income_money)