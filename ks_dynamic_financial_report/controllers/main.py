# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import content_disposition, request
from odoo.http import serialize_exception as _serialize_exception
from odoo.tools import html_escape

import json


class ksDynamicFinancialReportController(http.Controller):

    @http.route(['/dfr/pdf/download'], type='http', auth='public', methods=['POST'], csrf=False)
    def download_pdf_report(self, **post):
        # Support both FormData (new JS) and JSON-RPC body (cached old JS)
        if not post.get('id'):
            try:
                body = request.httprequest.get_json(force=True, silent=True)
                if body and isinstance(body, dict):
                    params = body.get('params', body)
                    post = {k: v for k, v in params.items() if v is not None}
            except Exception:
                pass
        id = post.get('id')
        data = json.loads(post.get('data', '{}')) if isinstance(post.get('data'), str) else (post.get('data') or {})
        context = json.loads(post.get('context', '{}')) if isinstance(post.get('context'), str) else (post.get('context') or {})
        reportname = post.get('reportname')
        if not id or not reportname:
            return request.make_response('Missing id or reportname', status=400)
        try:
            pdf = request.env['ir.actions.report'].sudo().with_context(context)._render_qweb_pdf(reportname, id, data)[0]
        except Exception as e:
            return request.make_response(f'Report rendering failed: {html_escape(str(e))}', status=500)
        return request.make_response(pdf, headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', f'{reportname}.pdf'),
            ('Content-Length', len(pdf)),
        ])

    @http.route('/ks_dynamic_financial_report', type='http', auth='user', methods=['POST'], csrf=False)
    def get_report(self, model, ks_df_informations, output_format, financial_id=None, **kw):
        uid = request.session.uid
        ks_dynamic_report_model = request.env['ks.dynamic.financial.base']
        ks_df_informations = json.loads(ks_df_informations)
        cids = request.httprequest.cookies.get('cids', str(request.env.user.company_id.id))
        allowed_company_ids = [int(cid) for cid in cids.split(',')]
        ks_dynamic_report_instance = request.env[model].with_user(uid).with_context(
            allowed_company_ids=allowed_company_ids)
        if financial_id and financial_id != 'null':
            ks_dynamic_report_instance = ks_dynamic_report_instance.browse(int(financial_id))
        ks_dynamic_report_name = ks_dynamic_report_instance.report_name if ks_dynamic_report_instance.report_name else ks_dynamic_report_instance.display_name
        try:
            if output_format == 'xlsx':
                # self.ks_df_report_account_report_ids = self
                # if self.id == self.env.ref('ks_dynamic_financial_reports.ks_df_tb0').id:
                response = request.make_response(
                    None,
                    headers=[
                        ('Content-Type', ks_dynamic_report_model.ks_get_export_plotting_type('xlsx')),
                        ('Content-Disposition', content_disposition(ks_dynamic_report_name + '.xlsx'))
                    ]
                )
                if ks_dynamic_report_name == 'Trial Balance':
                    response.stream.write(ks_dynamic_report_instance.ks_get_xlsx_trial_balance(ks_df_informations))
                elif ks_dynamic_report_name == 'General Ledger':
                    response.stream.write(ks_dynamic_report_instance.ks_get_xlsx_general_ledger(ks_df_informations))
                elif ks_dynamic_report_name == 'Partner Ledger':
                    response.stream.write(ks_dynamic_report_instance.ks_get_xlsx_partner_ledger(ks_df_informations))
                elif ks_dynamic_report_name == 'Age Receivable':
                    response.stream.write(ks_dynamic_report_instance.ks_get_xlsx_Aging(ks_df_informations))
                elif ks_dynamic_report_name == 'Age Payable':
                    response.stream.write(ks_dynamic_report_instance.ks_get_xlsx_Aging(ks_df_informations))
                elif ks_dynamic_report_name == 'Tax Report':
                    response.stream.write(ks_dynamic_report_instance.ks_dynamic_tax_xlsx(ks_df_informations))
                elif ks_dynamic_report_name == 'Consolidate Journal':
                    response.stream.write(ks_dynamic_report_instance.ks_dynamic_consolidate_xlsx(ks_df_informations))
                else:
                    response.stream.write(ks_dynamic_report_instance.get_xlsx(ks_df_informations))
            return response
        except Exception as e:
            se = _serialize_exception(e)
            error = {
                'code': 200,
                'message': 'Odoo Server Error',
                'data': se
            }
            return request.make_response(html_escape(json.dumps(error)))
