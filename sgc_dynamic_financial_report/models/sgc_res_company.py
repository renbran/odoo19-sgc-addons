# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import api, fields, models


class ResCompany(models.Model):
    """Extend ``res.company`` with SGC DFR configuration fields.

    These settings allow per-company customisation of the financial reports,
    such as header/footer text, logo overrides, and default report options.
    """

    _inherit = "res.company"

    # ── Report Configuration ─────────────────────────────────────────
    sgc_dfr_report_header = fields.Text(
        string="Report Header Text",
        help="Custom text displayed at the top of every SGC financial report "
             "for this company. Leave empty to use the default header.",
    )
    sgc_dfr_report_footer = fields.Text(
        string="Report Footer Text",
        help="Custom text displayed at the bottom of every SGC financial report "
             "for this company. Leave empty to use the default footer.",
    )
    sgc_dfr_logo = fields.Binary(
        attachment=True,
        string="Report Logo",
        help="Optional company logo used in SGC financial reports. "
             "If not set, the company logo is used.",
    )
    sgc_dfr_show_currency_symbol = fields.Boolean(
        string="Show Currency Symbol in Reports",
        default=True,
        help="When enabled, the currency symbol is shown alongside amounts "
             "in report headers and totals.",
    )
    sgc_dfr_decimal_precision = fields.Integer(
        string="Decimal Precision",
        default=2,
        help="Number of decimal places used for monetary amounts in reports.",
    )
    sgc_dfr_negative_format = fields.Selection(
        selection=[
            ("minus", "-1,234.56"),
            ("parentheses", "(1,234.56)"),
            ("red", "1,234.56 in red"),
        ],
        string="Negative Number Format",
        default="minus",
        help="How negative amounts are displayed in exported reports.",
    )
    sgc_dfr_aging_buckets = fields.Char(
        string="Aging Bucket Intervals (days)",
        default="0-30,31-60,61-90,91-180,>180",
        help="Comma-separated list of aging bucket definitions used in "
             "Aged Receivable and Aged Payable reports. Each bucket is "
             "defined as 'min-max' or '>min'.",
    )
    sgc_dfr_enable_comparison = fields.Boolean(
        string="Enable Period Comparison by Default",
        default=False,
        help="When enabled, the comparison period fields in the report "
             "wizard are shown and pre-filled by default.",
    )

    @api.onchange("sgc_dfr_decimal_precision")
    def _onchange_sgc_dfr_decimal_precision(self):
        if self.sgc_dfr_decimal_precision and (
            self.sgc_dfr_decimal_precision < 0
            or self.sgc_dfr_decimal_precision > 6
        ):
            raise models.ValidationError(
                "Decimal precision must be between 0 and 6."
            )