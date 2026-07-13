# -*- coding: utf-8 -*-
from odoo import api, models, _

class ProjectSoAReport(models.AbstractModel):
    _name = 'report.sgc_construction_management.report_project_soa'
    _description = 'Project Statement of Account Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['construction.project'].browse(docids)

        report_data = {}
        for project in docs:
            if not project.analytic_account_id:
                report_data[project.id] = {'invoices': [], 'bills': []}
                continue

            analytic_id_str = str(project.analytic_account_id.id)

            # Fetch all posted move lines related to the project's analytic account
            # Note: analytic_distribution is a JSON field. In Odoo 17/19, 'in' with a list of
            # analytic account ids matches a line whose distribution contains ANY of them.
            lines = self.env['account.move.line'].search([
                ('parent_state', '=', 'posted'),
                ('analytic_distribution', 'in', [project.analytic_account_id.id]),
                ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'))
            ])

            # Group unique moves
            moves = lines.mapped('move_id')
            invoices = moves.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund')).sorted('invoice_date')
            bills = moves.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund')).sorted('invoice_date')

            report_data[project.id] = {
                'invoices': invoices,
                'bills': bills,
            }

        return {
            'doc_ids': docids,
            'doc_model': 'construction.project',
            'docs': docs,
            'report_data': report_data,
        }
