# -*- coding: utf-8 -*-
import base64

from datetime import datetime
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrWpsWizard(models.TransientModel):
    _name = 'eh.uae.wps.wizard'
    _description = 'UAE WPS SIF File Generator'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Payslip Batch',
        required=True,
    )
    date = fields.Date(
        string='Salary Date',
        required=True,
        default=fields.Date.today,
    )
    employer_mohre_id = fields.Char(
        string='Employer MOHRE ID',
        size=13,
        required=True,
        help='MOHRE-issued employer ID for WPS.',
    )
    company_bank_account = fields.Char(
        string='Company IBAN',
        size=23,
        required=True,
        help='Employer IBAN debited for the payroll.',
    )
    sif_filename = fields.Char(
        string='SIF File Name',
        readonly=True,
    )
    sif_content = fields.Text(
        string='SIF File Content',
        readonly=True,
    )
    sif_file = fields.Binary(
        string='SIF File',
        readonly=True,
        attachment=False,
    )
    employee_count = fields.Integer(
        string='Employees',
        readonly=True,
    )
    total_amount = fields.Float(
        string='Total Amount (AED)',
        readonly=True,
        digits=(16, 2),
    )

    def _sif_company_header(self):
        self.ensure_one()
        company = self.company_id
        vdate = self.date.strftime('%Y%m%d')
        employer_id = (self.employer_mohre_id or '').ljust(13)[:13]
        employer_name = (company.name or '').ljust(40)[:40]
        return (
            '1'  # Record type
            + vdate  # Salary date YYYYMMDD
            + employer_id  # Employer MOHRE ID
            + employer_name
            + 'AED'  # Currency
        ).ljust(199) + '\n'

    def _sif_employee_line(self, payslip):
        self.ensure_one()
        employee = payslip.employee_id
        contract = payslip.contract_id
        wps_id = (employee.wps_employee_id or '').ljust(14)[:14]
        name = (employee.name or '').ljust(40)[:40]
        bank_code = (employee.wps_bank_id.bic or '').ljust(9)[:9]
        agent_id = (contract.wps_agent_id or '').ljust(9)[:9]
        routing = (contract.wps_routing_code or '').ljust(9)[:9]
        iban = (employee.wps_iban or '').ljust(23)[:23]
        net_line = payslip.line_ids.filtered(lambda l: l.code == 'NET')
        net_amount = int(round(net_line[0].total if net_line else payslip.contract_id.wage or 0))
        amount_str = str(net_amount).zfill(15)
        ref_no = str(payslip.id or 0).zfill(18)
        return (
            '2'
            + wps_id
            + name
            + bank_code
            + agent_id
            + routing
            + iban
            + amount_str
            + ref_no
        ).ljust(199) + '\n'

    def _sif_footer(self, count, total):
        self.ensure_one()
        return (
            '3'
            + str(count).zfill(9)
            + str(int(round(total))).zfill(15)
        ).ljust(199) + '\n'

    def action_generate(self):
        self.ensure_one()
        run = self.payslip_run_id
        slips = run.slip_ids.filtered(lambda s: s.state != 'cancel')
        if not slips:
            raise UserError(_('Selected payslip batch has no payslips to process.'))
        lines = []
        total = 0.0
        count = 0
        lines.append(self._sif_company_header())
        for slip in slips:
            net_line = slip.line_ids.filtered(lambda l: l.code == 'NET')
            net = net_line[0].total if net_line else (slip.contract_id.wage or 0.0)
            if net <= 0:
                continue
            lines.append(self._sif_employee_line(slip))
            total += net
            count += 1
        lines.append(self._sif_footer(count, total))
        content = ''.join(lines)
        filename = 'WPS_%s_%s.sif' % (
            self.company_id.vat or 'CO',
            self.date.strftime('%Y%m%d'),
        )
        self.write({
            'sif_filename': filename,
            'sif_content': content,
            'sif_file': base64.b64encode(content.encode('utf-8')),
            'employee_count': count,
            'total_amount': total,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eh.uae.wps.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_download(self):
        self.ensure_one()
        if not self.sif_content:
            self.action_generate()
        return {
            'type': 'ir.actions.act_url',
            'url': ('/web/content/eh.uae.wps.wizard/%d/sif_file/%s?download=true'
                    % (self.id, self.sif_filename or 'wps.sif')),
            'target': 'self',
        }

    def action_print_pdf(self):
        """Print the WPS batch summary PDF report."""
        self.ensure_one()
        if not self.sif_content:
            self.action_generate()
        return self.env.ref('eh_uae_payroll_wps.action_report_wps_batch').report_action(self)

    def action_export_xlsx(self):
        """Export WPS batch data as Excel spreadsheet."""
        self.ensure_one()
        if not self.sif_content:
            self.action_generate()
        return self.env.ref('eh_uae_payroll_wps.action_report_wps_batch_xlsx').report_action(self)
