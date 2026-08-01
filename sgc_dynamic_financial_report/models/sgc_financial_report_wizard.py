# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from datetime import date, timedelta

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
    ("budget_vs_actual", "Budget vs Actual"),
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
    # Multi-company consolidation.  Aggregates amounts across the
    # root company + every child company (via parent_id hierarchy).
    # Default False keeps single-company behavior identical.
    consolidate_companies = fields.Boolean(
        string="Consolidate Companies",
        default=False,
        help="Include the wizard's company and all its child companies in the "
             "report.  When enabled, ``currency_id`` is used as the reporting "
             "currency and amounts are converted from each company's native "
             "currency before aggregation.",
    )
    # Reporting currency.  Defaults to the company's currency so the
    # single-company path is byte-identical to the legacy report.
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Reporting Currency",
        default=lambda self: self.env.company.currency_id,
        help="Display currency for all amounts.  Defaults to the company's "
             "currency.  When different, the engine converts each move line "
             "from its source currency using the rate on the report's start "
             "date.",
    )
    # Optional subset of companies the user wants consolidated.  Empty
    # means "use the wizard company + every child (the default for the
    # consolidation flag)"; a non-empty selection narrows the scope
    # without changing the multi-company logic.
    company_ids = fields.Many2many(
        comodel_name="res.company",
        relation="sgc_dfr_wizard_company_rel",
        string="Companies to Consolidate",
        help="Subset of companies to consolidate when 'Consolidate "
             "Companies' is enabled. Leave empty to use the wizard "
             "company plus every child company.",
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

    # ── Budget Options ──────────────────────────────────────────────
    show_budget_vs_actual = fields.Boolean(
        string="Show Budget vs Actual",
        default=False,
        help="Append Budget, Actual, Variance and Variance % columns to "
             "Balance Sheet, Profit & Loss and Trial Balance reports. "
             "Budget figures come from the ``sgc.dfr.budget`` records "
             "matching the wizard's start-date fiscal year.",
    )

    # ── Analytic Breakdown ──────────────────────────────────────────
    # Per-line analytic breakdown: when True, the engine expands each
    # row with one extra column per analytic account from the wizard
    # filter (or per account actually used, if the filter is empty).
    # The SQL already supports ``analytic_account_ids``; this only
    # affects the HTML/XLSX rendering.
    analytic_breakdown = fields.Boolean(
        string="Include Analytic Breakdown",
        default=False,
        help="Add analytic account columns to report lines.",
    )

    # ── Scheduled Reports ────────────────────────────────────────────
    # This is a *flag* (not a stored schedule). The Schedule button in
    # the wizard view passes it through the ir.cron bridge so the cron
    # runner knows which payload to recreate. Storing it on the wizard
    # lets the action handler build a stable, JSON-serialisable summary
    # of the report params for the cron job.
    schedule_name = fields.Char(
        string="Schedule Name",
        help="Friendly label used when the report is scheduled to run "
             "automatically. Leave empty to skip scheduling.",
    )
    schedule_cron_id = fields.Many2one(
        comodel_name="ir.cron",
        string="Scheduled Job",
        readonly=True,
        ondelete="set null",
        help="Cron job that re-runs this report on the configured "
             "schedule. Set by the 'Schedule This Report' button.",
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
            self.comparison_date_to = self.date_from - timedelta(days=1)
            self.comparison_date_from = self.comparison_date_to - timedelta(
                days=days_diff
            )

    @api.onchange("consolidate_companies")
    def _onchange_consolidate_companies(self):
        """When consolidation turns off, fall back to the home currency."""
        if not self.consolidate_companies:
            self.currency_id = self.env.company.currency_id

    @api.onchange("company_id")
    def _onchange_company_id_consolidation(self):
        """Sync the target currency when the lead company changes."""
        if not self.consolidate_companies:
            self.currency_id = self.company_id.currency_id

    # ── Report generation ────────────────────────────────────────────
    def action_generate_report(self, for_print=False):
        """Generate HTML and store it on ``result_html``.

        Retained as a programmatic API for the test suite and any cron
        jobs that need to materialise a report without going through the
        enterprise preview UI. The legacy ``ir.actions.act_window`` return
        (which opened ``sgc_dfr_wizard_view_result``) was removed when
        that view itself was deleted — UI flow now goes exclusively
        through the metadata-driven enterprise client action.

        ``for_print`` sets ``sgc_dfr_for_print`` on the engine's context,
        which makes every collapsible section render pre-expanded and
        drops the on-screen-only "Expand All / Collapse All" toolbar -
        a PDF is a static document with no click events, so relying on
        collapse state (or `@media print` CSS forcing) is not reliable
        across wkhtmltopdf versions; ``action_print_pdf`` passes
        ``for_print=True`` so the generated HTML is correct at the
        source rather than depending on print-time CSS.
        """
        self.ensure_one()
        # sgc.financial.report.engine is an AbstractModel (no table) - it
        # can't be .create()'d, its methods are called on the bare recordset.
        engine = self.env["sgc.financial.report.engine"].with_context(
            wizard_id=self.id,
            sgc_dfr_for_print=for_print,
        )
        result = engine._generate_report(self)
        self.write({
            "result_html": result.get("html", ""),
            "state": "computed",
        })
        return True

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
        """Export the report as a PDF file.

        Uses a single generic ``ir.actions.report`` (``sgc_report_pdf``,
        bound to ``sgc_financial_report_template``) rather than a
        per-report-type template - the template renders generically via
        ``object.result_html`` and ``object.report_type``.

        ``result_html`` is refreshed here because the enterprise preview
        UI keeps the HTML in client-side state; the server-side
        ``result_html`` field only reflects what ``action_generate_report``
        last wrote. Calling it first ensures the PDF reflects whatever
        filters the user most recently applied via the preview bar.

        ``for_print=True`` forces every collapsible section fully
        expanded in the generated HTML (see ``action_generate_report``) -
        a PDF can never receive the "Expand All" click, so the sections
        must already be open in the HTML that gets rendered.
        """
        self.ensure_one()
        self.action_generate_report(for_print=True)
        report_action = self.env.ref("sgc_dynamic_financial_report.sgc_report_pdf")
        return report_action.report_action(self)

    def action_schedule_report(self):
        """Create an ``ir.cron`` job that re-runs this report on a schedule.

        The wizard itself is transient, so we serialise its params into the
        cron's ``code`` payload and recreate the wizard there on each tick.
        Re-running the same wizard re-emits ``action_export_xlsx`` (or the
        chosen downstream action) which is the "fire-and-forget" report.
        """
        self.ensure_one()
        if not self.schedule_name:
            raise UserError(
                _("Please set a Schedule Name before scheduling this report.")
            )
        cron = self.env["ir.cron"].sudo().create({
            "name": f"SGC DFR: {self.schedule_name}",
            "model_id": self.env["ir.model"]._get_id(self._name),
            "state": "code",
            "code": self._build_cron_code(),
            "interval_number": 1,
            "interval_type": "days",
            "active": True,
            "doall": False,
        })
        self.schedule_cron_id = cron
        return {
            "type": "ir.client.tag",
            "tag": "display_notification",
            "params": {
                "title": _("Scheduled"),
                "message": _("Report '%s' scheduled to run daily.") % self.schedule_name,
                "type": "success",
                "sticky": False,
            },
        }

    def _build_cron_code(self):
        """Serialise wizard params into a Python snippet the cron can run.

        The cron re-creates a transient wizard from this snapshot via the
        dedicated ``_cron_replay_snapshot`` helper below, which accepts a
        single ``dict`` argument. Encoded JSON is safe to embed as a
        Python literal (the cron ``code`` field is evaluated with
        ``eval`` semantics, but our helper only ever reads from a passed
        dict so there's no risk of injection).
        """
        import json

        snapshot = {
            "report_type": self.report_type,
            "company_id": self.company_id.id,
            "date_from": fields.Date.to_string(self.date_from),
            "date_to": fields.Date.to_string(self.date_to),
            "enable_comparison": self.enable_comparison,
            "comparison_date_from": (
                fields.Date.to_string(self.comparison_date_from)
                if self.comparison_date_from else False
            ),
            "comparison_date_to": (
                fields.Date.to_string(self.comparison_date_to)
                if self.comparison_date_to else False
            ),
            "account_ids": self.account_ids.ids,
            "account_group_ids": self.account_group_ids.ids,
            "target_move": self.target_move,
            "partner_ids": self.partner_ids.ids,
            "partner_category_id": self.partner_category_id.id or False,
            "analytic_account_ids": self.analytic_account_ids.ids,
            "journal_ids": self.journal_ids.ids,
            "show_hierarchy": self.show_hierarchy,
            "show_zero_balance": self.show_zero_balance,
            "hide_parent_hierarchy": self.hide_parent_hierarchy,
            "tax_grid": self.tax_grid,
            "consolidate_companies": self.consolidate_companies,
            "currency_id": self.currency_id.id,
            "company_ids": self.company_ids.ids,
            "show_budget_vs_actual": self.show_budget_vs_actual,
            "analytic_breakdown": self.analytic_breakdown,
        }
        encoded = json.dumps(snapshot)
        return (
            "env['sgc.financial.report.wizard']"
            "._cron_replay_snapshot(" + encoded + ")\n"
        )

    @api.model
    def _cron_replay_snapshot(self, snapshot):
        """Replay a scheduled report from a snapshot dict.

        Used as the entry point for ``ir.cron`` jobs created by
        ``action_schedule_report``. Re-creates a transient wizard from
        the snapshot and runs ``action_export_xlsx`` on it - the standard
        XLSX export is fire-and-forget (writes to the user's download
        bucket) so we deliberately do not return its action.
        """
        wizard = self.create(snapshot)
        return wizard.action_export_xlsx()