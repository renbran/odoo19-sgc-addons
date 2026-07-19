# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

REPORT_TYPE_SELECTION = [
    ("balance_sheet", "Balance Sheet"),
    ("profit_loss", "Profit & Loss"),
    ("cash_flow", "Cash Flow Statement"),
    ("trial_balance", "Trial Balance"),
    ("general_ledger", "General Ledger"),
    ("partner_ledger", "Partner Ledger"),
    ("aged_receivable", "Aged Receivable"),
    ("aged_payable", "Aged Payable"),
    ("tax_report", "Tax Report"),
]


class SgcFinancialReportWizard(models.TransientModel):
    """Transient wizard model for generating SGC Dynamic Financial Reports.

    This wizard collects user parameters (date range, company, accounts,
    analytic dimensions, output format) and dispatches to the appropriate
    report engine for data retrieval and rendering.
    """

    _name = "sgc.financial.report.wizard"
    _description = "SGC Financial Report Wizard"
    _rec_name = "report_type"

    # ── Report Type ──────────────────────────────────────────────────
    report_type = fields.Selection(
        selection=REPORT_TYPE_SELECTION,
        string="Report Type",
        required=True,
        default="balance_sheet",
    )

    # ── Company ──────────────────────────────────────────────────────
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # ── Date Filtering ───────────────────────────────────────────────
    date_from = fields.Date(
        string="Start Date",
        required=True,
        default=lambda self: self._default_date_from(),
    )
    date_to = fields.Date(
        string="End Date",
        required=True,
        default=lambda self: self._default_date_to(),
    )

    # ── Comparison Period (optional) ─────────────────────────────────
    enable_comparison = fields.Boolean(
        string="Enable Comparison",
        default=False,
    )
    comparison_date_from = fields.Date(
        string="Comparison Start Date",
    )
    comparison_date_to = fields.Date(
        string="Comparison End Date",
    )

    # ── Account Filtering ────────────────────────────────────────────
    account_ids = fields.Many2many(
        comodel_name="account.account",
        relation="sgc_dfr_wizard_account_rel",
        string="Accounts",
        # account.account dropped its single company_id in favor of a
        # company_ids Many2many (17+ shared chart of accounts) - this is
        # the same domain idiom account_move_views.xml uses for account_id.
        domain="[('company_ids', 'parent_of', company_id)]",
    )
    account_group_ids = fields.Many2many(
        comodel_name="account.group",
        relation="sgc_dfr_wizard_account_group_rel",
        string="Account Groups",
    )
    target_move = fields.Selection(
        selection=[
            ("posted", "All Posted Entries"),
            ("all", "All Entries"),
            ("draft", "Draft Entries Only"),
        ],
        string="Target Moves",
        required=True,
        default="posted",
    )

    # ── Partner Filtering ────────────────────────────────────────────
    partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="sgc_dfr_wizard_partner_rel",
        string="Partners",
        domain="['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]",
    )
    partner_category_id = fields.Many2one(
        comodel_name="res.partner.category",
        string="Partner Tag",
    )

    # ── Analytic Filtering ───────────────────────────────────────────
    # account.analytic.tag was removed from Odoo (17+ moved to a JSON
    # analytic_distribution field with no separate "tags" concept) - only
    # analytic account filtering remains.
    analytic_account_ids = fields.Many2many(
        comodel_name="account.analytic.account",
        relation="sgc_dfr_wizard_analytic_rel",
        string="Analytic Accounts",
    )

    # ── Journal Filtering ────────────────────────────────────────────
    journal_ids = fields.Many2many(
        comodel_name="account.journal",
        relation="sgc_dfr_wizard_journal_rel",
        string="Journals",
        domain="[('company_id', '=', company_id)]",
    )

    # ── Output Options ───────────────────────────────────────────────
    show_hierarchy = fields.Boolean(
        string="Show Account Hierarchy",
        default=True,
    )
    show_zero_balance = fields.Boolean(
        string="Show Zero Balance Accounts",
        default=False,
    )
    hide_parent_hierarchy = fields.Boolean(
        string="Hide Parent Hierarchy",
        default=False,
    )

    # ── Tax-specific Options ─────────────────────────────────────────
    tax_grid = fields.Boolean(
        string="Tax Grid Layout",
        default=False,
    )

    # ── Internal state ───────────────────────────────────────────────
    result_html = fields.Html(
        string="Report Result",
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("computed", "Computed"),
        ],
        string="State",
        default="draft",
    )

    # ── Default helpers ──────────────────────────────────────────────
    @api.model
    def _default_date_from(self):
        """Return the first day of the current fiscal year."""
        today = fields.Date.today()
        company = self.env.company
        if company.fiscalyear_last_month and company.fiscalyear_last_day:
            # Compute the current fiscal year start
            last_month = int(company.fiscalyear_last_month)
            last_day = int(company.fiscalyear_last_day)
            fiscal_year_end = date(today.year, last_month, last_day)
            if today > fiscal_year_end:
                fiscal_year_start = date(today.year + 1, 1, 1)
            else:
                fiscal_year_start = date(today.year, 1, 1)
            return fiscal_year_start
        return date(today.year, 1, 1)

    @api.model
    def _default_date_to(self):
        """Return today's date."""
        return fields.Date.today()

    # ── Constraints ──────────────────────────────────────────────────
    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError(
                    _("The start date must be earlier than or equal to the end date.")
                )

    @api.onchange("enable_comparison")
    def _onchange_enable_comparison(self):
        if self.enable_comparison and self.date_from and self.date_to:
            days_diff = (self.date_to - self.date_from).days
            self.comparison_date_to = self.date_from - fields.timedelta(days=1)
            self.comparison_date_from = self.comparison_date_to - fields.timedelta(
                days=days_diff
            )

    # ── Report generation ────────────────────────────────────────────
    def action_generate_report(self):
        """Generate the financial report and display it in the result view."""
        self.ensure_one()
        # sgc.financial.report.engine is an AbstractModel (no table) - it
        # can't be .create()'d, its methods are called on the bare recordset.
        engine = self.env["sgc.financial.report.engine"].with_context(
            wizard_id=self.id,
        )
        result = engine._generate_report(self)
        self.write({
            "result_html": result.get("html", ""),
            "state": "computed",
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "sgc_dynamic_financial_report.sgc_dfr_wizard_view_result"
            ).id,
            "target": "new",
        }

    def action_export_xlsx(self):
        """Export the report as an Excel (XLSX) file.

        Routes to the appropriate XLSX report action based on ``report_type``.
        """
        self.ensure_one()
        report_xml_id_map = {
            "balance_sheet": "sgc_dynamic_financial_report.sgc_report_balance_sheet",
            "profit_loss": "sgc_dynamic_financial_report.sgc_report_profit_loss",
            "cash_flow": "sgc_dynamic_financial_report.sgc_report_cash_flow",
            "trial_balance": "sgc_dynamic_financial_report.sgc_report_trial_balance",
            "general_ledger": "sgc_dynamic_financial_report.sgc_report_general_ledger",
            "partner_ledger": "sgc_dynamic_financial_report.sgc_report_partner_ledger",
            "aged_receivable": "sgc_dynamic_financial_report.sgc_report_aged_receivable",
            "aged_payable": "sgc_dynamic_financial_report.sgc_report_aged_payable",
            "tax_report": "sgc_dynamic_financial_report.sgc_report_tax_report",
        }
        report_xml_id = report_xml_id_map.get(self.report_type)
        if not report_xml_id:
            raise UserError(
                _("No XLSX report defined for report type '%s'.") % self.report_type
            )
        report_action = self.env.ref(report_xml_id)
        return report_action.report_action(self)

    def action_print_pdf(self):
        """Print the report as PDF (client-side render of HTML result)."""
        self.ensure_one()
        return {
            "type": "ir.actions.report",
            "report_name": "sgc_dynamic_financial_report.sgc_financial_report_template",
            "report_type": "qweb-pdf",
            "model": self._name,
            "ids": self.ids,
            "context": {"active_ids": self.ids},
        }