# -*- coding: utf-8 -*-
import io

import xlsxwriter

from odoo import http
from odoo.http import request

WORK_TYPE_LABELS = {
    'civil': 'Civil',
    'structural': 'Structural',
    'electrical': 'Electrical',
    'plumbing': 'Plumbing/MEP',
    'finishing': 'Finishing',
    'external': 'External Works',
    'other': 'Other',
}


class ConstructionXlsxExport(http.Controller):

    def _xlsx_response(self, workbook, output, filename):
        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="%s"' % filename),
            ],
        )

    @http.route('/sgc_construction_management/xlsx/boq/<int:boq_id>', type='http', auth='user')
    def export_boq_xlsx(self, boq_id, **kwargs):
        # browse (not sudo) so normal ir.rule/access checks still apply to the
        # requesting user, same as the existing qweb-pdf report.
        boq = request.env['construction.boq'].browse(boq_id)
        boq.check_access('read')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('BOQ')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1f2937', 'font_color': 'white'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})
        bold_money_fmt = workbook.add_format({'bold': True, 'num_format': '#,##0.00'})
        section_fmt = workbook.add_format({'bold': True})

        sheet.write_row(0, 0, ['Item No.', 'Description', 'UOM', 'Quantity', 'Unit Rate', 'Amount', 'WBS Phase'], header_fmt)
        sheet.set_column(1, 1, 40)
        sheet.set_column(0, 0, 12)
        sheet.set_column(2, 6, 14)

        row = 1
        for work_type, label in WORK_TYPE_LABELS.items():
            lines = boq.line_ids.filtered(lambda l: l.work_type == work_type and not l.is_section)
            if not lines:
                continue
            sheet.write(row, 0, label, section_fmt)
            row += 1
            for line in lines:
                sheet.write(row, 0, line.item_no or '')
                sheet.write(row, 1, line.description or '')
                sheet.write(row, 2, line.uom_id.name or '')
                sheet.write(row, 3, line.qty)
                sheet.write(row, 4, line.unit_rate, money_fmt)
                sheet.write(row, 5, line.amount, money_fmt)
                sheet.write(row, 6, line.wbs_id.name or '')
                row += 1
            sheet.write(row, 5, sum(lines.mapped('amount')), bold_money_fmt)
            row += 1

        row += 1
        sheet.write(row, 4, 'GRAND TOTAL', section_fmt)
        sheet.write(row, 5, boq.total_amount, bold_money_fmt)

        return self._xlsx_response(workbook, output, 'BOQ - %s.xlsx' % (boq.ref or boq.name))

    @http.route('/sgc_construction_management/xlsx/wip/<int:project_id>', type='http', auth='user')
    def export_wip_xlsx(self, project_id, **kwargs):
        project = request.env['construction.project'].browse(project_id)
        project.check_access('read')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('WIP')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1f2937', 'font_color': 'white'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})

        sheet.write_row(0, 0, ['Metric', 'Value'], header_fmt)
        sheet.set_column(0, 0, 40)
        sheet.set_column(1, 1, 20)

        earned_revenue = project.contract_value * (project.progress / 100)
        over_under = earned_revenue - project.total_billed

        rows = [
            ('Contract Value', project.contract_value),
            ('Actual Progress %', project.progress),
            ('Earned Revenue (Contract Value x Progress %)', earned_revenue),
            ('Total Billed to Date', project.total_billed),
            ('Over / (Under) Billing', over_under),
            ('Total Expenses Incurred', project.total_expenses),
            ('Current Margin %', project.margin_percent),
        ]
        for i, (label, value) in enumerate(rows, start=1):
            sheet.write(i, 0, label)
            sheet.write(i, 1, value, money_fmt)

        return self._xlsx_response(workbook, output, 'WIP - %s.xlsx' % project.name)

    @http.route('/sgc_construction_management/xlsx/soa/<int:partner_id>', type='http', auth='user')
    def export_soa_xlsx(self, partner_id, **kwargs):
        partner = request.env['res.partner'].browse(partner_id)
        partner.check_access('read')

        invoices = request.env['account.move'].search([
            ('partner_id', '=', partner.id),
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('state', '=', 'posted'),
        ], order='invoice_date asc, id asc')

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Statement of Account')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1f2937', 'font_color': 'white'})
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'num_format': 'yyyy-mm-dd'})

        sheet.write_row(0, 0, ['Date', 'Reference', 'Description', 'Amount', 'Balance'], header_fmt)
        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 2, 28)
        sheet.set_column(3, 4, 16)

        balance = 0.0
        for i, inv in enumerate(invoices, start=1):
            amount = inv.amount_total if inv.move_type == 'out_invoice' else -inv.amount_total
            balance += amount
            if inv.invoice_date:
                sheet.write_datetime(i, 0, inv.invoice_date, date_fmt)
            sheet.write(i, 1, inv.name or '')
            sheet.write(i, 2, inv.ref or '')
            sheet.write(i, 3, amount, money_fmt)
            sheet.write(i, 4, balance, money_fmt)

        return self._xlsx_response(workbook, output, 'SOA - %s.xlsx' % partner.name)
