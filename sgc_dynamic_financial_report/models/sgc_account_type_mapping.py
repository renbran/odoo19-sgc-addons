# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import fields, models

import logging

_logger = logging.getLogger(__name__)

FINANCIAL_SECTION_SELECTION = [
    ("assets", "Assets"),
    ("liabilities", "Liabilities"),
    ("equity", "Equity"),
    ("revenue", "Revenue"),
    ("expenses", "Expenses"),
    ("other", "Other"),
]

# ``account.account.type`` was removed from Odoo in v17 - ``account.account``
# now carries its type directly as this selection field. Kept in sync with
# ``account.account.account_type``'s own selection values.
ACCOUNT_TYPE_SELECTION = [
    ("asset_receivable", "Receivable"),
    ("asset_cash", "Bank and Cash"),
    ("asset_current", "Current Assets"),
    ("asset_non_current", "Non-current Assets"),
    ("asset_prepayments", "Prepayments"),
    ("asset_fixed", "Fixed Assets"),
    ("liability_payable", "Payable"),
    ("liability_credit_card", "Credit Card"),
    ("liability_current", "Current Liabilities"),
    ("liability_non_current", "Non-current Liabilities"),
    ("equity", "Equity"),
    ("equity_unaffected", "Current Year Earnings"),
    ("income", "Income"),
    ("income_other", "Other Income"),
    ("expense", "Expenses"),
    ("expense_depreciation", "Depreciation"),
    ("expense_direct_cost", "Cost of Revenue"),
    ("off_balance", "Off-Balance Sheet"),
]


class SgcDfrAccountType(models.Model):
    """Maps an Odoo account type to a financial statement section.

    This mapping is the backbone of the report engine's classification logic.
    For example, the account type ``'asset_receivable'`` maps to the
    ``'assets'`` financial section, which causes all accounts of that type
    to appear under the Assets heading in the Balance Sheet.
    """

    _name = "sgc.dfr.account.type"
    _description = "SGC Account Type to Financial Section Mapping"
    _order = "sequence, id"
    _rec_name = "account_type"

    # ── Fields ───────────────────────────────────────────────────────
    account_type = fields.Selection(
        selection=ACCOUNT_TYPE_SELECTION,
        string="Account Type",
        required=True,
        index=True,
        help="The internal type code of the Odoo account "
             "(e.g. 'asset_receivable', 'income', 'expense').",
    )
    financial_section = fields.Selection(
        selection=FINANCIAL_SECTION_SELECTION,
        string="Financial Section",
        required=True,
        index=True,
        help="The financial statement section where accounts of this type "
             "should appear (Assets, Liabilities, Equity, Revenue, Expenses, Other).",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Determines the display order within the financial section.",
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # ── Constraints ──────────────────────────────────────────────────
    # Odoo 19 replaced the `_sql_constraints` list attribute with
    # declarative `models.Constraint` class attributes - the old-style
    # declaration is silently not enforced (registry logs a warning, no
    # constraint is created).
    _account_type_uniq = models.Constraint(
        "UNIQUE(account_type, company_id)",
        "Each account type can only be mapped once per company.",
    )