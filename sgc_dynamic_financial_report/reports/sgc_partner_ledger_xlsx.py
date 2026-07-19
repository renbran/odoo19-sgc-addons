# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import models


class SgcPartnerLedgerXlsx(models.AbstractModel):
    """XLSX renderer for the SGC Partner Ledger report."""

    _name = "report.sgc_dynamic_financial_report.sgc_partner_ledger_xlsx"
    _description = "SGC Partner Ledger XLSX Report"
    _inherit = "report.report_xlsx.abstract"

    def _get_report_name(self):
        return "SGC_Partner_Ledger"

    def generate_xlsx_report(self, workbook, data, wizard):
        """Generate the Partner Ledger Excel file.

        Args:
            workbook: xlsxwriter Workbook instance.
            data: Dict passed from the wizard.
            wizard: ``sgc.financial.report.wizard`` recordset.
        """
        # ── Fetch data from the report engine ───────────────────────
        engine = wizard.env["sgc.financial.report.engine"]
        result = engine._generate_report(wizard)
        report_data = result.get("data", {})
        partner_balances = report_data.get("partner_balances", [])
        partner_lines = report_data.get("partner_lines", {})

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
        fmt_partner_header = workbook.add_format({
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
        fmt_subtotal = workbook.add_format({
            "bold": True,
            "size": 10,
            "bg_color": "#E2EFDA",
            "border": 1,
            "valign": "vcenter",
        })
        fmt_subtotal_money = workbook.add_format({
            "bold": True,
            "size": 10,
            "bg_color": "#E2EFDA",
            "border": 1,
            "num_format": "#,##0.00",
            "valign": "vcenter",
        })

        # ── Shared header writing helper ────────────────────────────
        def _write_header(sheet):
            sheet.write(0, 0, wizard.company_id.name or "", fmt_title)
            sheet.write(1, 0, "Partner Ledger", fmt_title)
            sheet.write(2, 0, date_range, fmt_date)

        # ═══════════════════════════════════════════════════════════
        # Sheet 1 – Partner Summary
        # ═══════════════════════════════════════════════════════════
        sheet_summary = workbook.add_worksheet("Partner Summary")

        # Column widths: A=Partner, B=Ref, C=Debit, D=Credit, E=Balance
        sheet_summary.set_column("A:A", 40)
        sheet_summary.set_column("B:B", 18)
        sheet_summary.set_column("C:C", 18)
        sheet_summary.set_column("D:D", 18)
        sheet_summary.set_column("E:E", 18)

        _write_header(sheet_summary)
        row = 4

        summary_headers = [
            "Partner",
            "Ref",
            "Debit",
            "Credit",
            "Balance",
        ]
        for col_idx, header in enumerate(summary_headers):
            sheet_summary.write(row, col_idx, header, fmt_col_header)
        row += 1

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

            sheet_summary.write(row, 0, partner.get("partner_name") or "", fmt_normal)
            sheet_summary.write(row, 1, partner.get("partner_ref") or "", fmt_normal)
            sheet_summary.write(row, 2, debit, fmt_money)
            sheet_summary.write(row, 3, credit, fmt_money)
            sheet_summary.write(row, 4, balance, fmt_money)
            row += 1

        # Grand total row
        sheet_summary.write(row, 0, "", fmt_total)
        sheet_summary.write(row, 1, "TOTAL", fmt_total)
        sheet_summary.write(row, 2, grand_debit, fmt_total_money)
        sheet_summary.write(row, 3, grand_credit, fmt_total_money)
        sheet_summary.write(row, 4, grand_balance, fmt_total_money)

        # ═══════════════════════════════════════════════════════════
        # Sheet 2 – Transaction Details
        # ═══════════════════════════════════════════════════════════
        sheet_details = workbook.add_worksheet("Transaction Details")

        # Column widths
        sheet_details.set_column("A:A", 14)   # Date
        sheet_details.set_column("B:B", 16)   # Journal Entry
        sheet_details.set_column("C:C", 35)   # Description
        sheet_details.set_column("D:D", 18)   # Account
        sheet_details.set_column("E:E", 18)   # Debit
        sheet_details.set_column("F:F", 18)   # Credit

        _write_header(sheet_details)
        row = 4

        detail_headers = [
            "Date",
            "Journal Entry",
            "Description",
            "Account",
            "Debit",
            "Credit",
        ]

        # Sort partners by name for consistent output
        sorted_partner_ids = sorted(
            partner_lines.keys(),
            key=lambda pid: (partner_lines[pid].get("partner_name") or "").lower(),
        )

        for idx, partner_id in enumerate(sorted_partner_ids):
            partner_data = partner_lines[partner_id]
            partner_name = partner_data.get("partner_name") or ""
            partner_ref = partner_data.get("partner_ref") or ""
            p_lines = partner_data.get("lines", [])
            p_total_debit = float(partner_data.get("total_debit") or 0.0)
            p_total_credit = float(partner_data.get("total_credit") or 0.0)

            # Partner heading row
            heading_text = partner_name
            if partner_ref:
                heading_text = f"{partner_name} ({partner_ref})"
            sheet_details.write(row, 0, heading_text, fmt_partner_header)
            for col in range(1, 6):
                sheet_details.write(row, col, "", fmt_partner_header)
            row += 1

            # Column headers for this partner's mini-table
            for col_idx, header in enumerate(detail_headers):
                sheet_details.write(row, col_idx, header, fmt_col_header)
            row += 1

            # Transaction lines
            for line in p_lines:
                debit = float(line.get("debit") or 0.0)
                credit = float(line.get("credit") or 0.0)

                sheet_details.write(row, 0, line.get("date") or "", fmt_date_value)
                sheet_details.write(row, 1, line.get("move_name") or "", fmt_normal)
                sheet_details.write(row, 2, line.get("entry_name") or "", fmt_normal)
                sheet_details.write(row, 3, line.get("account_code") or "", fmt_normal)
                sheet_details.write(row, 4, debit, fmt_money)
                sheet_details.write(row, 5, credit, fmt_money)
                row += 1

            # Partner subtotal row
            sheet_details.write(row, 0, "", fmt_subtotal)
            sheet_details.write(row, 1, "", fmt_subtotal)
            sheet_details.write(row, 2, f"Total {partner_name}", fmt_subtotal)
            sheet_details.write(row, 3, "", fmt_subtotal)
            sheet_details.write(row, 4, p_total_debit, fmt_subtotal_money)
            sheet_details.write(row, 5, p_total_credit, fmt_subtotal_money)
            row += 1

            # Add 2 blank rows between partners (skip after the last one)
            if idx < len(sorted_partner_ids) - 1:
                row += 2