# -*- coding: utf-8 -*-
import io
from odoo import models, api, _
import xlsxwriter
import datetime
from datetime import date
from odoo.exceptions import ValidationError


class KsDynamicFinancialXlsxAR(models.Model):
    _inherit = 'ks.dynamic.financial.base'

    def round_nested_values(self, data):
        """Recursively round all float/int values in nested dicts, lists, or tuples."""
        if isinstance(data, dict):
            return {k: self.round_nested_values(v) for k, v in data.items()}
        elif isinstance(data, (list, tuple)):
            return type(data)(self.round_nested_values(v) for v in data)
        elif isinstance(data, (int, float)):
            return round(data, 2)
        return data

    def get_xlsx(self, ks_df_informations, response=None):
        if self.ks_name in ('Executive Summary', 'Balance Sheet', 'Profit and Loss', 'Cash Flow Statement'):
            if ks_df_informations['date']['ks_start_date'] == False and ks_df_informations['date'][
                'ks_end_date'] == False:
                raise ValidationError(_('Sorry,Export file will not get download without date.'))
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet(self.display_name[:31])
            if self.display_name == "Cash Flow Statement":
                lines, ks_initial_balance, ks_current_balance, ks_ending_balance = self.with_context(no_format=True,
                                                                                                     print_mode=True,
                                                                                                     prefetch_fields=False).ks_fetch_report_account_lines(
                    ks_df_informations)
                lines = self.round_nested_values(lines)
                lines = self.maintain_hierarchy(lines)

                def sum_children_totals(node):
                    if not node.get("children"):
                        return {
                            "debit": node.get("debit", 0.0),
                            "credit": node.get("credit", 0.0),
                            "balance": node.get("balance", 0.0),
                        }

                    total_debit = 0.0
                    total_credit = 0.0
                    total_balance = 0.0

                    for child in node["children"]:
                        child_totals = sum_children_totals(child)
                        total_debit += child_totals["debit"]
                        total_credit += child_totals["credit"]
                        total_balance += child_totals["balance"]

                    node["debit"] = round(total_debit, 2)
                    node["credit"] = round(total_credit, 2)
                    node["balance"] = round(total_balance, 2)

                    return {
                        "debit": node["debit"],
                        "credit": node["credit"],
                        "balance": node["balance"],
                    }

                for root in lines:
                    name = root.get("ks_name", "")
                    if name not in [
                        "Cash and cash equivalents, beginning period",
                        "Cash and cash equivalents,beginning period"
                    ]:
                        sum_children_totals(root)

                net_increase = None
                beginning_balance = None
                closing_balance = None

                for line in lines:
                    name = line.get("ks_name", "")
                    if name == "Net increase in cash and cash equivalents":
                        net_increase = line
                    elif name in (
                    "Cash and cash equivalents,beginning period", "Cash and cash equivalents, beginning period"):
                        beginning_balance = line
                    elif name in ("Cash and cash equivalents, closing balance"):
                        closing_balance = line

                if beginning_balance:
                    totals = sum_children_totals(beginning_balance)
                    beginning_balance["debit"] = totals["debit"]
                    beginning_balance["credit"] = totals["credit"]
                    beginning_balance["balance"] = totals["balance"]

                if net_increase and beginning_balance and closing_balance:
                    closing_balance["debit"] = round(
                        net_increase.get("debit", 0.0) + beginning_balance.get("debit", 0.0), 2)
                    closing_balance["credit"] = round(
                        net_increase.get("credit", 0.0) + beginning_balance.get("credit", 0.0), 2)
                    closing_balance["balance"] = round(
                        net_increase.get("balance", 0.0) + beginning_balance.get("balance", 0.0), 2)

                lines = self.flatten_hierarchy(lines)
            elif self.display_name != "Executive Summary":
                lines, ks_initial_balance, ks_current_balance, ks_ending_balance = self.with_context(no_format=True,
                                                                                                     print_mode=True,
                                                                                                     prefetch_fields=False).ks_fetch_report_account_lines(
                    ks_df_informations)
            else:
                lines = self.ks_process_executive_summary(ks_df_informations)
            if self.display_name == self.env.ref(
                    'ks_dynamic_financial_report.ks_dynamic_financial_balancesheet').display_name:
                ks_bal_sum = 0
                for line in lines:

                    # if line.get('ks_name') == 'LIABILITIES' or line.get('ks_name') == 'EQUITY':
                    #     ks_bal_sum += line.get('balance', 0)

                    if line.get('ks_name') == 'Previous Years Unallocated Earnings' and \
                            ks_df_informations['date']['ks_process'] == 'range':
                        ks_bal_sum -= line.get('balance', 0)
                lines[len(lines) - 1]['balance'] = ks_bal_sum

            ks_company_id = self.env['res.company'].sudo().browse(ks_df_informations.get('company_id'))

            sheet.freeze_panes(4, 1)
            row_pos = 0
            row_pos_2 = 0
            format_title = workbook.add_format({
                'bold': True,
                'align': 'center',
                'font_size': 12,
                'border': False,
                'font': 'Arial',
            })
            format_header = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
                'bottom': False
            })
            content_header = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
            })
            content_header_date = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
                # 'num_format': 'dd/mm/yyyy',
            })
            line_header = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'right',
                'font': 'Arial',
                'bottom': True
            })
            line_header.set_num_format(
                '#,##0.' + '0' * ks_company_id.currency_id.decimal_places or 2)
            line_header_bold = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'right',
                'font': 'Arial',
                'bottom': True
            })
            line_header_bold.set_num_format(
                '#,##0.' + '0' * ks_company_id.currency_id.decimal_places or 2)
            line_header_string = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'left',
                'font': 'Arial',
                'bottom': True
            })
            line_header_string_bold = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'left',
                'font': 'Arial',
                'bottom': True
            })
            # Date from
            lang = self.env.user.lang
            lang_id = self.env['res.lang'].search([('code', '=', lang)])['date_format'].replace('/', '-')
            f_s_date = ks_df_informations['date'].get('ks_start_date') if ks_df_informations['date'].get(
                'ks_start_date') else date.today()
            f_e_date = ks_df_informations['date'].get('ks_end_date') if ks_df_informations['date'].get(
                'ks_end_date') else date.today()
            ks_new_start_date = (datetime.datetime.strptime(
                str(f_s_date), '%Y-%m-%d').date()).strftime(lang_id)
            ks_new_end_date = (datetime.datetime.strptime(
                str(f_e_date), '%Y-%m-%d').date()).strftime(lang_id)

            if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                if not ks_df_informations['ks_differ'].get('ks_intervals'):
                    f_start_date = date.today()
                    f_end_date = date.today()
                    ks_new_start_comp_date = (datetime.datetime.strptime(
                        str(f_start_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                    ks_new_end_comp_date = (datetime.datetime.strptime(
                        str(f_end_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                else:
                    for_s_start_comp_date = ks_df_informations['ks_differ'].get('ks_intervals')[-1][
                        'ks_start_date'] if \
                        ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_start_date'] else date.today()
                    for_e_end_comp_date = ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_end_date'] if \
                        ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_end_date'] else date.today()
                    ks_new_start_comp_date = (datetime.datetime.strptime(
                        str(for_s_start_comp_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                    ks_new_end_comp_date = (datetime.datetime.strptime(
                        str(for_e_end_comp_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
            if self.display_name != 'Executive Summary':
                if not ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    if ks_df_informations['date']['ks_process'] == 'range':
                        sheet.write_string(row_pos_2, 0, _('Date From'), format_header)
                        if ks_df_informations['date'].get('ks_start_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_start_date,
                                               content_header_date)
                        row_pos_2 += 1
                        # Date to
                        sheet.write_string(row_pos_2, 0, _('Date To'), format_header)

                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)
                    else:
                        sheet.write_string(row_pos_2, 0, _('As of Date'), format_header)
                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2 + 1, row_pos_2, ks_new_end_date,
                                               content_header_date)
                    # Accounts
                    row_pos_2 += 1
                    if ks_df_informations.get('analytic_accounts'):
                        sheet.write_string(row_pos_2, 0, _('Analytic Accounts'), format_header)
                        a_list = ', '.join(lt or '' for lt in ks_df_informations['selected_analytic_account_names'])
                        sheet.write_string(row_pos_2, 1, a_list, content_header)
                    # Tags
                    row_pos_2 += 1
                    if ks_df_informations.get('analytic_tags'):
                        sheet.write_string(row_pos_2, 0, _('Tags'), format_header)
                        a_list = ', '.join(lt or '' for lt in ks_df_informations['selected_analytic_tag_names'])
                        sheet.write_string(row_pos_2, 1, a_list, content_header)

                # Comparison filter
                if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    sheet.write_string(row_pos_2, 0, _('Comparison Date From'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_start_comp_date,
                                       content_header_date)
                    row_pos_2 += 1
                    # Date to
                    sheet.write_string(row_pos_2, 0, _('Comparison Date To'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_end_comp_date,
                                       content_header_date)

                row_pos_2 += 0
                sheet.write_string(2 - 2, 2, _('Journals'),
                                   format_header)
                j_list = ', '.join(
                    journal.get('code') or '' for journal in ks_df_informations['journals'] if journal.get('selected'))
                sheet.write_string(1, 2, j_list,
                                   content_header)

                # Account
                row_pos_2 += 0
                sheet.write_string(2 - 2, 3, _('Accounts'), format_header)
                j_list = ', '.join(
                    journal.get('name') or '' for journal in ks_df_informations['account'] if journal.get('selected'))
                sheet.write_string(1, 3, j_list,
                                   content_header)

                row_pos += 3
                if ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 90)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)

                    sheet.write_string(row_pos, 1, _('Debit'),
                                       format_header)
                    sheet.write_string(row_pos, 2, _('Credit'),
                                       format_header)
                    sheet.write_string(row_pos, 3, _('Balance'),
                                       format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        sheet.write_number(row_pos, 1, float(a.get('debit', 0.0)), tmp_style_num)
                        sheet.write_number(row_pos, 2, float(a.get('credit', 0.0)), tmp_style_num)
                        sheet.write_number(row_pos, 3, float(a.get('balance', 0.0)), tmp_style_num)

                if not ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:
                    sheet.set_column(0, 0, 105)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 2, 15)
                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)
                    if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                        col_pos = 0
                        for i in lines[0]['balance_cmp']:
                            sheet.write_string(row_pos, col_pos + 1, i.split('comp_bal_')[1],
                                               format_header),
                            sheet.write_string(row_pos, (col_pos + 1) + 1, _('Balance'),
                                               format_header)
                            col_pos = col_pos + 1
                    else:
                        sheet.write_string(row_pos, 1, _('Balance'),
                                           format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                            col_pos = 0
                            for i in a['balance_cmp']:
                                sheet.write_number(row_pos, col_pos + 1, float(a['balance_cmp'][i]), tmp_style_num)
                                sheet.write_number(row_pos, (col_pos + 1) + 1, float(a['balance']), tmp_style_num)
                                col_pos += 1
            else:
                if not ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    if ks_df_informations['date']['ks_process'] == 'range':
                        sheet.write_string(row_pos_2, 0, _('Date From'),
                                           format_header)
                        if ks_df_informations['date'].get('ks_start_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_start_date,
                                               content_header_date)
                        row_pos_2 += 1
                        # Date to
                        sheet.write_string(row_pos_2, 0, _('Date To'),
                                           format_header)

                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)
                    else:
                        sheet.write_string(row_pos_2, 0, _('As of Date'),
                                           format_header)
                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)

                if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    sheet.write_string(row_pos_2, 0, _('Comparison Date From'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_start_comp_date,
                                       content_header_date)
                    row_pos_2 += 1
                    # Date to
                    sheet.write_string(row_pos_2, 0, _('Comparison Date To'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_end_comp_date,
                                       content_header_date)

                row_pos += 3
                sheet.write_string(2 - 2, 3, _('Accounts'), format_header)
                j_list = ', '.join(
                    journal.get('name') or '' for journal in ks_df_informations['account'] if journal.get('selected'))
                sheet.write_string(2 - 1, 3, j_list,
                                   content_header)
                if ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 90)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)

                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)
                    sheet.write_string(row_pos, 1, _('Debit'),
                                       format_header)
                    sheet.write_string(row_pos, 2, _('Credit'),
                                       format_header)
                    sheet.write_string(row_pos, 3, _('Balance'),
                                       format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        if a.get('debit'):
                            for i in a.get('debit'):
                                sheet.write_number(row_pos, 1, float(a.get('debit', 0.0)[i]), tmp_style_num)
                        if a.get('credit'):
                            for i in a.get('credit'):
                                sheet.write_number(row_pos, 2, float(a.get('credit', 0.0)[i]), tmp_style_num)
                        if a.get('balance'):
                            for i in a.get('balance'):
                                sheet.write_number(row_pos, 3, float(a.get('balance', 0.0)[i]), tmp_style_num)

                if not ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 50)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)
                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)

                    sheet.write_string(row_pos, 1, ks_df_informations['date']['ks_string'],
                                       format_header)
                    ks_col = 2
                    # for x in range(3):
                    for i in ks_df_informations['ks_differ']['ks_intervals']:
                        sheet.write_string(row_pos, ks_col, i['ks_string'],
                                           format_header)
                        sheet.set_column(ks_col, ks_col, 20)
                        ks_col += 1

                    ks_col_line = 0
                    for line in lines:
                        sheet.write(row_pos + 1, 0, line['ks_name'],
                                    line_header_string)
                        if line.get('balance'):
                            for ks in line.get('balance'):
                                sheet.write(row_pos + 1, ks_col_line + 1, line.get('balance')[ks],
                                            line_header)
                                ks_col_line += 1
                        ks_col_line = 0
                        row_pos += 1

            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()

            return generated_file
        else:
            if ks_df_informations['date']['ks_start_date'] == False and ks_df_informations['date'][
                'ks_end_date'] == False:
                raise ValidationError(_('Sorry,Export file will not get download without date.'))
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            sheet = workbook.add_worksheet(self.display_name[:31])
            if self.display_name != "Executive Summary":
                lines, ks_initial_balance, ks_current_balance, ks_ending_balance = self.with_context(no_format=True,
                                                                                                     print_mode=True,
                                                                                                     prefetch_fields=False).ks_fetch_report_account_lines(
                    ks_df_informations)
            else:
                lines = self.ks_process_executive_summary(ks_df_informations)
            if self.display_name == self.env.ref(
                    'ks_dynamic_financial_report.ks_dynamic_financial_balancesheet').display_name:
                ks_bal_sum = 0
                for line in lines:

                    # if line.get('ks_name') == 'LIABILITIES' or line.get('ks_name') == 'EQUITY':
                    #     ks_bal_sum += line.get('balance', 0)

                    if line.get('ks_name') == 'Previous Years Unallocated Earnings' and \
                            ks_df_informations['date']['ks_process'] == 'range':
                        ks_bal_sum -= line.get('balance', 0)
                lines[len(lines) - 1]['balance'] = ks_bal_sum

            ks_company_id = self.env['res.company'].sudo().browse(ks_df_informations.get('company_id'))

            sheet.freeze_panes(4, 1)
            row_pos = 0
            row_pos_2 = 0
            format_title = workbook.add_format({
                'bold': True,
                'align': 'center',
                'font_size': 12,
                'border': False,
                'font': 'Arial',
            })
            format_header = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
                'bottom': False
            })
            content_header = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
            })
            content_header_date = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'center',
                'font': 'Arial',
                # 'num_format': 'dd/mm/yyyy',
            })
            line_header = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'right',
                'font': 'Arial',
                'bottom': True
            })
            line_header.set_num_format(
                '#,##0.' + '0' * ks_company_id.currency_id.decimal_places or 2)
            line_header_bold = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'right',
                'font': 'Arial',
                'bottom': True
            })
            line_header_bold.set_num_format(
                '#,##0.' + '0' * ks_company_id.currency_id.decimal_places or 2)
            line_header_string = workbook.add_format({
                'bold': False,
                'font_size': 10,
                'align': 'left',
                'font': 'Arial',
                'bottom': True
            })
            line_header_string_bold = workbook.add_format({
                'bold': True,
                'font_size': 10,
                'align': 'left',
                'font': 'Arial',
                'bottom': True
            })
            # Date from
            lang = self.env.user.lang
            lang_id = self.env['res.lang'].search([('code', '=', lang)])['date_format'].replace('/', '-')
            f_s_date = ks_df_informations['date'].get('ks_start_date') if ks_df_informations['date'].get(
                'ks_start_date') else date.today()
            f_e_date = ks_df_informations['date'].get('ks_end_date') if ks_df_informations['date'].get(
                'ks_end_date') else date.today()
            ks_new_start_date = (datetime.datetime.strptime(
                str(f_s_date), '%Y-%m-%d').date()).strftime(lang_id)
            ks_new_end_date = (datetime.datetime.strptime(
                str(f_e_date), '%Y-%m-%d').date()).strftime(lang_id)

            if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                if not ks_df_informations['ks_differ'].get('ks_intervals'):
                    f_start_date = date.today()
                    f_end_date = date.today()
                    ks_new_start_comp_date = (datetime.datetime.strptime(
                        str(f_start_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                    ks_new_end_comp_date = (datetime.datetime.strptime(
                        str(f_end_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                else:
                    for_s_start_comp_date = ks_df_informations['ks_differ'].get('ks_intervals')[-1][
                        'ks_start_date'] if \
                        ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_start_date'] else date.today()
                    for_e_end_comp_date = ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_end_date'] if \
                        ks_df_informations['ks_differ'].get('ks_intervals')[-1]['ks_end_date'] else date.today()
                    ks_new_start_comp_date = (datetime.datetime.strptime(
                        str(for_s_start_comp_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
                    ks_new_end_comp_date = (datetime.datetime.strptime(
                        str(for_e_end_comp_date), '%Y-%m-%d').date()).strftime(
                        lang_id)
            if self.display_name != 'Executive Summary':
                if not ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    if ks_df_informations['date']['ks_process'] == 'range':
                        sheet.write_string(row_pos_2, 0, _('Date From'), format_header)
                        if ks_df_informations['date'].get('ks_start_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_start_date,
                                               content_header_date)
                        row_pos_2 += 1
                        # Date to
                        sheet.write_string(row_pos_2, 0, _('Date To'), format_header)

                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)
                    else:
                        sheet.write_string(row_pos_2, 0, _('As of Date'), format_header)
                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2 + 1, row_pos_2, ks_new_end_date,
                                               content_header_date)
                    # Accounts
                    row_pos_2 += 1
                    if ks_df_informations.get('analytic_accounts'):
                        sheet.write_string(row_pos_2, 0, _('Analytic Accounts'), format_header)
                        a_list = ', '.join(lt or '' for lt in ks_df_informations['selected_analytic_account_names'])
                        sheet.write_string(row_pos_2, 1, a_list, content_header)
                    # Tags
                    row_pos_2 += 1
                    if ks_df_informations.get('analytic_tags'):
                        sheet.write_string(row_pos_2, 0, _('Tags'), format_header)
                        a_list = ', '.join(lt or '' for lt in ks_df_informations['selected_analytic_tag_names'])
                        sheet.write_string(row_pos_2, 1, a_list, content_header)

                # Comparison filter
                if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    sheet.write_string(row_pos_2, 0, _('Comparison Date From'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_start_comp_date,
                                       content_header_date)
                    row_pos_2 += 1
                    # Date to
                    sheet.write_string(row_pos_2, 0, _('Comparison Date To'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_end_comp_date,
                                       content_header_date)

                row_pos_2 += 0
                sheet.write_string(2 - 2, 2, _('Journals'),
                                   format_header)
                j_list = ', '.join(
                    journal.get('code') or '' for journal in ks_df_informations['journals'] if journal.get('selected'))
                sheet.write_string(1, 2, j_list,
                                   content_header)

                # Account
                row_pos_2 += 0
                sheet.write_string(2 - 2, 3, _('Accounts'), format_header)
                j_list = ', '.join(
                    journal.get('name') or '' for journal in ks_df_informations['account'] if journal.get('selected'))
                sheet.write_string(1, 3, j_list,
                                   content_header)

                row_pos += 3
                if ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 90)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)

                    sheet.write_string(row_pos, 1, _('Debit'),
                                       format_header)
                    sheet.write_string(row_pos, 2, _('Credit'),
                                       format_header)
                    sheet.write_string(row_pos, 3, _('Balance'),
                                       format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        sheet.write_number(row_pos, 1, float(a.get('debit', 0.0)), tmp_style_num)
                        sheet.write_number(row_pos, 2, float(a.get('credit', 0.0)), tmp_style_num)
                        sheet.write_number(row_pos, 3, float(a.get('balance', 0.0)), tmp_style_num)

                if not ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:
                    sheet.set_column(0, 0, 105)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 2, 15)
                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)
                    if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                        col_pos = 0
                        for i in lines[0]['balance_cmp']:
                            sheet.write_string(row_pos, col_pos + 1, i.split('comp_bal_')[1],
                                               format_header),
                            sheet.write_string(row_pos, (col_pos + 1) + 1, _('Balance'),
                                               format_header)
                            col_pos = col_pos + 1
                    else:
                        sheet.write_string(row_pos, 1, _('Balance'),
                                           format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                            col_pos = 0
                            for i in a['balance_cmp']:
                                sheet.write_number(row_pos, col_pos + 1, float(a['balance_cmp'][i]), tmp_style_num)
                                sheet.write_number(row_pos, (col_pos + 1) + 1, float(a['balance']), tmp_style_num)
                                col_pos += 1
            else:
                if not ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    if ks_df_informations['date']['ks_process'] == 'range':
                        sheet.write_string(row_pos_2, 0, _('Date From'),
                                           format_header)
                        if ks_df_informations['date'].get('ks_start_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_start_date,
                                               content_header_date)
                        row_pos_2 += 1
                        # Date to
                        sheet.write_string(row_pos_2, 0, _('Date To'),
                                           format_header)

                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)
                    else:
                        sheet.write_string(row_pos_2, 0, _('As of Date'),
                                           format_header)
                        if ks_df_informations['date'].get('ks_end_date'):
                            sheet.write_string(row_pos_2, 1, ks_new_end_date,
                                               content_header_date)

                if ks_df_informations['ks_diff_filter']['ks_diff_filter_enablity']:
                    sheet.write_string(row_pos_2, 0, _('Comparison Date From'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_start_comp_date,
                                       content_header_date)
                    row_pos_2 += 1
                    # Date to
                    sheet.write_string(row_pos_2, 0, _('Comparison Date To'),
                                       format_header)

                    sheet.write_string(row_pos_2, 1,
                                       ks_new_end_comp_date,
                                       content_header_date)

                row_pos += 3
                sheet.write_string(2 - 2, 3, _('Accounts'), format_header)
                j_list = ', '.join(
                    journal.get('name') or '' for journal in ks_df_informations['account'] if journal.get('selected'))
                sheet.write_string(2 - 1, 3, j_list,
                                   content_header)
                if ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 90)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)

                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)
                    sheet.write_string(row_pos, 1, _('Debit'),
                                       format_header)
                    sheet.write_string(row_pos, 2, _('Credit'),
                                       format_header)
                    sheet.write_string(row_pos, 3, _('Balance'),
                                       format_header)

                    for a in lines:
                        if a['ks_level'] == 2:
                            row_pos += 1
                        row_pos += 1
                        if a.get('account', False):
                            tmp_style_str = line_header_string
                            tmp_style_num = line_header
                        else:
                            tmp_style_str = line_header_string_bold
                            tmp_style_num = line_header_bold
                        sheet.write_string(row_pos, 0, '   ' * len(a.get('list_len', [])) + a.get('ks_name'),
                                           tmp_style_str)
                        if a.get('debit'):
                            for i in a.get('debit'):
                                sheet.write_number(row_pos, 1, float(a.get('debit', 0.0)[i]), tmp_style_num)
                        if a.get('credit'):
                            for i in a.get('credit'):
                                sheet.write_number(row_pos, 2, float(a.get('credit', 0.0)[i]), tmp_style_num)
                        if a.get('balance'):
                            for i in a.get('balance'):
                                sheet.write_number(row_pos, 3, float(a.get('balance', 0.0)[i]), tmp_style_num)

                if not ks_df_informations['ks_diff_filter']['ks_debit_credit_visibility']:

                    sheet.set_column(0, 0, 50)
                    sheet.set_column(1, 1, 15)
                    sheet.set_column(2, 3, 15)
                    sheet.set_column(3, 3, 15)
                    sheet.write_string(row_pos, 0, _('Name'),
                                       format_header)

                    sheet.write_string(row_pos, 1, ks_df_informations['date']['ks_string'],
                                       format_header)
                    ks_col = 2
                    # for x in range(3):
                    for i in ks_df_informations['ks_differ']['ks_intervals']:
                        sheet.write_string(row_pos, ks_col, i['ks_string'],
                                           format_header)
                        sheet.set_column(ks_col, ks_col, 20)
                        ks_col += 1

                    ks_col_line = 0
                    for line in lines:
                        sheet.write(row_pos + 1, 0, line['ks_name'],
                                    line_header_string)
                        if line.get('balance'):
                            for ks in line.get('balance'):
                                sheet.write(row_pos + 1, ks_col_line + 1, line.get('balance')[ks],
                                            line_header)
                                ks_col_line += 1
                        ks_col_line = 0
                        row_pos += 1

            workbook.close()
            output.seek(0)
            generated_file = output.read()
            output.close()

            return generated_file

    def maintain_hierarchy(self, report_lines):
        tree = {}
        items = {}
        has_hierarchy = False

        filtered_lines = [line for line in report_lines if line.get('ks_level') != 0]
        cloned_lines = [{**line, 'children': []} for line in filtered_lines]

        for line in cloned_lines:
            self_id = line['self_id']
            parent_id = line.get('parent')
            ks_level = line['ks_level']

            items[self_id] = line

            if ks_level == 1:
                tree[self_id] = line
                has_hierarchy = True
            else:
                if parent_id in items:
                    items[parent_id].setdefault('children', []).append(line)
                else:
                    items[parent_id] = {'children': [line]}

        return list(tree.values()) if has_hierarchy else filtered_lines

    def flatten_hierarchy(self, lines):
        """
        Flatten the hierarchical structure into a simple list.
        """
        result = []

        def recurse(line):
            result.append(line)
            for child in line.get('children', []):
                recurse(child)

        for line in lines:
            recurse(line)

        return result

