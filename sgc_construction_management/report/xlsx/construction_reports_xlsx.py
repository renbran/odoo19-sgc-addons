# -*- coding: utf-8 -*-
import io
import xlsxwriter
from odoo import models, fields, api

class ProjectWIPXlsx(models.AbstractModel):
    _name = 'report.sgc_construction_management.report_wip_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'WIP Report Excel'

    def generate_xlsx_report(self, workbook, data, projects):
        sheet = workbook.add_worksheet('WIP Report')

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        money = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        percent = workbook.add_format({'num_format': '0.00%', 'border': 1})
        header = workbook.add_format({'bold': True, 'size': 14, 'align': 'center'})
        border = workbook.add_format({'border': 1})

        sheet.merge_range('A1:G1', 'WORK IN PROGRESS (WIP) REPORT', header)

        # Headers
        headers = ['Project Name', 'Contract Value', 'Progress %', 'Earned Revenue', 'Total Billed', 'Over/(Under) Billing', 'Expenses']
        for col, title in enumerate(headers):
            sheet.write(2, col, title, bold)

        row = 3
        for project in projects:
            earned = (project.contract_value or 0) * ((project.progress or 0) / 100)
            over_under = earned - (project.total_billed or 0)

            sheet.write(row, 0, project.name, border)
            sheet.write(row, 1, project.contract_value or 0, money)
            sheet.write(row, 2, (project.progress or 0) / 100, percent)
            sheet.write(row, 3, earned, money)
            sheet.write(row, 4, project.total_billed or 0, money)
            sheet.write(row, 5, over_under, money)
            sheet.write(row, 6, project.total_expenses or 0, money)
            row += 1

        sheet.set_column('A:A', 30)
        sheet.set_column('B:G', 15)

class RABillingXlsx(models.AbstractModel):
    _name = 'report.sgc_construction_management.report_ra_billing_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'RA Billing Excel'

    def generate_xlsx_report(self, workbook, data, billings):
        sheet = workbook.add_worksheet('RA Billing')
        bold = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        money = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        border = workbook.add_format({'border': 1})

        sheet.write(0, 0, 'RA Billing Report', bold)

        headers = ['Item Description', 'Unit', 'BOQ Qty', 'Rate', 'Prev. Qty', 'Curr. Qty', 'Cum. Qty', 'Amount']
        for col, title in enumerate(headers):
            sheet.write(2, col, title, bold)

        row = 3
        for billing in billings:
            for line in billing.line_ids:
                sheet.write(row, 0, line.boq_line_description, border)
                sheet.write(row, 1, line.uom_id.name if line.uom_id else '', border)
                sheet.write(row, 2, line.boq_qty, border)
                sheet.write(row, 3, line.unit_rate, money)
                sheet.write(row, 4, line.qty_previous, border)
                sheet.write(row, 5, line.qty_current, border)
                sheet.write(row, 6, line.qty_cumulative, border)
                sheet.write(row, 7, line.amount, money)
                row += 1

        sheet.set_column('A:A', 40)
        sheet.set_column('B:H', 12)

class ProjectProfitabilityXlsx(models.AbstractModel):
    _name = 'report.sgc_construction_management.report_profitability_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Profitability Excel'

    def generate_xlsx_report(self, workbook, data, projects):
        sheet = workbook.add_worksheet('Profitability')
        bold = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        money = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        percent = workbook.add_format({'num_format': '0.00%', 'border': 1})
        border = workbook.add_format({'border': 1})

        sheet.write(0, 0, 'Project Profitability Report', bold)

        headers = ['Project Name', 'Contract Value', 'Total Billed', 'Direct Costs', 'Gross Margin', 'Margin %']
        for col, title in enumerate(headers):
            sheet.write(2, col, title, bold)

        row = 3
        for project in projects:
            margin = (project.total_billed or 0) - (project.total_expenses or 0)
            sheet.write(row, 0, project.name, border)
            sheet.write(row, 1, project.contract_value or 0, money)
            sheet.write(row, 2, project.total_billed or 0, money)
            sheet.write(row, 3, project.total_expenses or 0, money)
            sheet.write(row, 4, margin, money)
            sheet.write(row, 5, (project.margin_percent or 0) / 100, percent)
            row += 1

        sheet.set_column('A:A', 30)
        sheet.set_column('B:F', 15)
