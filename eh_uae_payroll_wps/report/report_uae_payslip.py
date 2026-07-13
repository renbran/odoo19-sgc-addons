# -*- coding: utf-8 -*-
# #############################################################################
#    UAE WPS Payroll - UAE Standard Payslip Report
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
# #############################################################################
from odoo import api, models


class ReportUaePayslip(models.AbstractModel):
    """UAE Standard Payslip Report with proper earnings/deductions grouping
    using salary rule category hierarchy instead of unreliable sign-based
    filtering."""

    _name = 'report.eh_uae_payroll_wps.report_payslipdetails_uae_wps'
    _description = 'UAE WPS Payslip Report'

    def _get_root_parent(self, category):
        """Traverse up the category hierarchy to find the root/top-level parent."""
        if category.parent_id:
            return self._get_root_parent(category.parent_id)
        return category

    def _get_uae_data(self, payslip):
        """Categorize payslip lines into Earnings, Deductions, and Employer
        Contributions using the salary rule category hierarchy.

        Returns a dict with keys:
          - earnings: list of {category_name, total, lines: [{name,code,total,...}]}
          - total_earnings: float
          - deductions: same structure
          - total_deductions: float
          - employer_contributions: same structure
          - total_employer_contributions: float
          - net_total: float
        """
        RuleCateg = self.env['hr.salary.rule.category']

        # Get lines that should appear on the payslip
        lines = payslip.mapped('line_ids').filtered(
            lambda r: r.appears_on_payslip and r.category_id)

        # Group lines by their immediate category
        categ_lines = {}
        for line in lines:
            categ_lines.setdefault(line.category_id.id, []).append(line)

        # Classify categories by root parent code convention.
        # SUMMARY categories (GROSS, NET) are tracked for validation but
        # excluded from Earning/Deduction/Employer grouping to avoid
        # double-counting.
        EARNING_CODES = {'BASIC', 'ALW', 'ALLOWANCE', 'EARNING', 'EARNINGS',
                         'OVERTIME', 'OT', 'COMMISSION', 'BONUS', 'INCENTIVE',
                         'SALES', 'TIP', 'REIMBURSEMENT',
                         'HRA', 'DA', 'TRAVEL', 'MEAL', 'MEDICAL', 'OTHER'}
        DEDUCTION_CODES = {'DED', 'DEDUCTION', 'DEDUCTIONS', 'LOAN', 'ABSENCE',
                           'PENALTY', 'FINE', 'INSURANCE', 'PENSION', 'GOSI'}
        EMPLOYER_CODES = {'ER', 'EMPLOYER', 'GOSI_ER', 'PENSION_ER',
                          'INSURANCE_ER', 'COMPANY'}
        NET_CODES = {'NET'}
        SUMMARY_CODES = {'GROSS'}

        # Additionally, any category whose parent has a deduction/employer code
        # inherits that classification
        def _classify(category):
            if not category:
                return 'earning'
            root = self._get_root_parent(category)
            root_code = (root.code or '').upper().strip()
            if root_code in NET_CODES:
                return 'net'
            if root_code in SUMMARY_CODES:
                return 'summary'
            if root_code in EARNING_CODES:
                return 'earning'
            if root_code in DEDUCTION_CODES:
                return 'deduction'
            if root_code in EMPLOYER_CODES:
                return 'employer'
            # Fallback: if it has no recognizable root code, check each parent
            # up the chain
            current = category
            while current:
                c = (current.code or '').upper().strip()
                if c in NET_CODES:
                    return 'net'
                if c in SUMMARY_CODES:
                    return 'summary'
                if c in DEDUCTION_CODES:
                    return 'deduction'
                if c in EMPLOYER_CODES:
                    return 'employer'
                if c in EARNING_CODES:
                    return 'earning'
                current = current.parent_id
            # Default: positive total → earnings, negative → deduction
            total = sum(l.total for l in categ_lines.get(category.id, []))
            return 'earning' if total >= 0 else 'deduction'

        earnings = []
        deductions = []
        employer_contributions = []
        net_total = 0.0

        for categ_id, line_list in categ_lines.items():
            category = RuleCateg.browse(categ_id)
            root = self._get_root_parent(category)
            total = sum(l.total for l in line_list)

            group_data = {
                'category_id': category.id,
                'category_name': root.name,
                'category_code': root.code,
                'sub_category_name': category.name if root != category else None,
                'total': abs(total),
                'lines': [],
            }
            for line in line_list:
                group_data['lines'].append({
                    'name': line.name or '',
                    'code': line.code or '',
                    'quantity': line.quantity or 0.0,
                    'amount': line.amount or 0.0,
                    'total': abs(line.total) if line.total else 0.0,
                    'raw_total': line.total or 0.0,
                })

            ctype = _classify(category)
            if ctype == 'earning':
                earnings.append(group_data)
            elif ctype == 'deduction':
                deductions.append(group_data)
            elif ctype == 'employer':
                employer_contributions.append(group_data)
            elif ctype == 'net':
                net_total = total

        # If no NET line found, compute from earnings - deductions
        if not net_total:
            total_earnings = sum(g['total'] for g in earnings)
            total_deductions = sum(g['total'] for g in deductions)
            net_total = total_earnings - total_deductions

        return {
            'earnings': earnings,
            'total_earnings': sum(g['total'] for g in earnings),
            'deductions': deductions,
            'total_deductions': sum(g['total'] for g in deductions),
            'employer_contributions': employer_contributions,
            'total_employer_contributions': sum(g['total'] for g in employer_contributions),
            'net_total': net_total,
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare report values for the UAE WPS payslip template."""
        payslips = self.env['hr.payslip'].browse(docids)
        uae_data = {}
        for payslip in payslips:
            uae_data[payslip.id] = self._get_uae_data(payslip)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': payslips,
            'data': data,
            'uae_data': uae_data,
        }
