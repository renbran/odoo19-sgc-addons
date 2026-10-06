from odoo import http
from odoo.http import content_disposition, request
from odoo.tools import html_escape
import json


class XLSXReportController(http.Controller):
    """Controller for XLSX report"""

    @http.route('/xlsx_report', type='http', auth='user', methods=['POST'], csrf=True)
    def get_report_xlsx(self, model, options, output_format, report_name, token=None, **kwargs):
        """Get XLSX report data"""
        try:
            # Validate input parameters
            if not model or not report_name or output_format != 'xlsx':
                return request.make_response(
                    'Invalid input parameters', status=400
                )

            report_obj = request.env[model]
            report_obj.check_access_rights('read')

            # Parse options
            options = json.loads(options)

            # Generate XLSX response
            response = request.make_response(
                None, headers=[
                    ('Content-Type', 'application/vnd.ms-excel'),
                    ('Content-Disposition', content_disposition(f"{report_name}.xlsx")),
                ]
            )
            report_obj.sudo().get_xlsx_report(options, response)
            response.set_cookie('fileToken', token or '')
            return response

        except ValueError as e:
            # Handle JSON parsing errors
            return request.make_response(
                f"Invalid JSON: {e}", status=400
            )
        except Exception as event:
            # General error handling
            serialize = http.serialize_exception(event)
            error = {
                'code': 500,
                'message': 'Odoo Server Error',
                'data': serialize
            }
            return request.make_response(html_escape(json.dumps(error)), status=500)
