# -*- coding: utf-8 -*-
from odoo import models


class WpsBatchXlsxReport(models.AbstractModel):
    _name = 'report.eh_uae_payroll_wps.wps_batch_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'WPS Batch Excel Report'

    def generate_xlsx_report(self, workbook, data, wizards):
        for wizard in wizards:
            bold = workbook.add_format({'bold': True})
            header_fmt = workbook.add_format({
                'bold': True, 'bg_color': '#1a5490',
                'font_color': '#ffffff', 'border': 1,
                'align': 'center', 'valign': 'vcenter',
            })
            label_fmt = workbook.add_format({'bold': True, 'bg_color': '#e8f0fe'})
            money_fmt = workbook.add_format({'num_format': '#,##0.00', 'align': 'right'})
            total_fmt = workbook.add_format({
                'bold': True, 'num_format': '#,##0.00',
                'align': 'right', 'bg_color': '#e8f0fe',
            })
            border_fmt = workbook.add_format({'border': 1})
            money_border = workbook.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})

            # ── Sheet 1: Summary ─────────────────────────────────────
            ws = workbook.add_worksheet('WPS Summary')
            ws.set_column(0, 0, 25)
            ws.set_column(1, 1, 35)

            ws.merge_range('A1:B1', 'UAE WPS BATCH SUMMARY', workbook.add_format({
                'bold': True, 'font_size': 14, 'bg_color': '#1a5490',
                'font_color': '#ffffff', 'align': 'center',
            }))
            rows = [
                ('Company', wizard.company_id.name or ''),
                ('MOHRE Employer ID', wizard.employer_mohre_id or ''),
                ('Payslip Batch', wizard.payslip_run_id.name or ''),
                ('Salary Date', str(wizard.date) if wizard.date else ''),
                ('Company IBAN', wizard.company_bank_account or ''),
                ('Total Employees', wizard.employee_count),
                ('Total Amount (AED)', wizard.total_amount),
                ('SIF File', wizard.sif_filename or 'Not generated'),
            ]
            for i, (label, value) in enumerate(rows, start=1):
                ws.write(i, 0, label, label_fmt)
                if label == 'Total Amount (AED)':
                    ws.write(i, 1, value, money_fmt)
                else:
                    ws.write(i, 1, value)

            # ── Sheet 2: Employee Details ─────────────────────────────
            ws2 = workbook.add_worksheet('Employee Details')
            headers = ['#', 'Employee Name', 'WPS ID', 'IBAN', 'Bank', 'Agent ID', 'Routing Code', 'Net Amount (AED)']
            col_widths = [5, 30, 18, 34, 22, 14, 14, 18]
            for col, (h, w) in enumerate(zip(headers, col_widths)):
                ws2.write(0, col, h, header_fmt)
                ws2.set_column(col, col, w)
            ws2.set_row(0, 18)

            slips = wizard.payslip_run_id.slip_ids.filtered(lambda s: s.state != 'cancel')
            total = 0.0
            for i, slip in enumerate(slips):
                net_line = slip.line_ids.filtered(lambda l: l.code == 'NET')
                net_amt = net_line[0].total if net_line else (slip.contract_id.wage or 0.0)
                row = i + 1
                ws2.write(row, 0, i + 1, border_fmt)
                ws2.write(row, 1, slip.employee_id.name or '', border_fmt)
                ws2.write(row, 2, slip.employee_id.wps_employee_id or '', border_fmt)
                ws2.write(row, 3, slip.employee_id.wps_iban or '', border_fmt)
                ws2.write(row, 4, slip.employee_id.wps_bank_id.name or '', border_fmt)
                ws2.write(row, 5, slip.contract_id.wps_agent_id or '', border_fmt)
                ws2.write(row, 6, slip.contract_id.wps_routing_code or '', border_fmt)
                ws2.write(row, 7, net_amt, money_border)
                total += net_amt

            # Total row
            total_row = len(slips) + 1
            ws2.merge_range(total_row, 0, total_row, 6, 'TOTAL', total_fmt)
            ws2.write(total_row, 7, total, total_fmt)
