# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import api, fields, models, _


class SgcDfrBudget(models.Model):
    """Budget header per account / company / fiscal year.

    Holds the total planned amount for an account over a fiscal year for
    budget-vs-actual reporting.  Per-month granularity lives on
    ``sgc.dfr.budget.line`` so a single header can be split into 12
    monthly buckets (or any subset) without duplicating header data.

    The header amount is the yearly total; ``line`` amounts are
    per-period breakdowns.  The engine treats the header ``amount`` as
    the canonical budget figure for variance computation, and falls
    back to summing ``line.amount`` when the header amount is unset.
    """

    _name = "sgc.dfr.budget"
    _description = "SGC DFR Budget"
    _order = "company_id, fiscal_year, account_id"
    _rec_name = "display_name"

    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Account",
        required=True,
        index=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    fiscal_year = fields.Char(
        string="Fiscal Year",
        required=True,
        size=4,
        help="Four-digit year (e.g. '2026'). Matched against the year of the "
             "wizard's start date during budget-vs-actual computation.",
    )
    amount = fields.Monetary(
        string="Budget Amount",
        currency_field="currency_id",
        help="Planned total amount for this account over the fiscal year.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    line_ids = fields.One2many(
        comodel_name="sgc.dfr.budget.line",
        inverse_name="budget_id",
        string="Monthly Lines",
    )
    active = fields.Boolean(default=True)

    @api.depends("account_id", "company_id", "fiscal_year", "amount")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.company_id.name} / {rec.fiscal_year} / "
                f"{rec.account_id.code or ''} {rec.account_id.name or ''}"
            )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=False,
    )

    _sql_constraints = [
        (
            "sgc_dfr_budget_unique",
            "UNIQUE (account_id, company_id, fiscal_year)",
            "A budget already exists for this account, company and fiscal year.",
        ),
    ]


class SgcDfrBudgetLine(models.Model):
    """Monthly breakdown of an SGC DFR Budget header.

    ``period`` is a fixed 12-slot selection (month1..month12) so the engine
    can JOIN directly without parsing free-text month labels; ``amount`` is
    in the parent header's currency.  ``analytic_account_id`` is optional
    so a single account can carry multiple analytic splits within one
    month if the customer needs that level of granularity.
    """

    _name = "sgc.dfr.budget.line"
    _description = "SGC DFR Budget Line"
    _order = "budget_id, period"

    budget_id = fields.Many2one(
        comodel_name="sgc.dfr.budget",
        string="Budget",
        required=True,
        ondelete="cascade",
        index=True,
    )
    account_id = fields.Many2one(
        comodel_name="account.account",
        string="Account",
        related="budget_id.account_id",
        store=True,
        index=True,
    )
    period = fields.Selection(
        selection=[
            ("month1", "January"),
            ("month2", "February"),
            ("month3", "March"),
            ("month4", "April"),
            ("month5", "May"),
            ("month6", "June"),
            ("month7", "July"),
            ("month8", "August"),
            ("month9", "September"),
            ("month10", "October"),
            ("month11", "November"),
            ("month12", "December"),
        ],
        string="Period",
        required=True,
    )
    amount = fields.Monetary(
        string="Amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Currency",
        related="budget_id.currency_id",
        store=True,
    )
    analytic_account_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Analytic Account",
    )
