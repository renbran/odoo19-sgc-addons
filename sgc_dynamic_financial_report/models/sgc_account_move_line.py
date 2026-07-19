# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    """Extend ``account.move.line`` with SGC DFR helper fields/methods.

    The additional computed field ``sgc_dfr_financial_section`` allows the
    report engine to classify lines without an extra JOIN at query time.
    """

    _inherit = "account.move.line"

    # ── Computed Fields ──────────────────────────────────────────────
    sgc_dfr_financial_section = fields.Selection(
        selection=[
            ("assets", "Assets"),
            ("liabilities", "Liabilities"),
            ("equity", "Equity"),
            ("revenue", "Revenue"),
            ("expenses", "Expenses"),
            ("other", "Other"),
        ],
        string="Financial Section",
        compute="_compute_sgc_dfr_financial_section",
        store=True,
        index=True,
        help="The financial statement section derived from the account type "
             "mapping configured in SGC Dynamic Financial Reports.",
    )

    @api.depends("account_id.account_type")
    def _compute_sgc_dfr_financial_section(self):
        """Resolve the financial section from the account type mapping."""
        Mapping = self.env["sgc.dfr.account.type"]
        # Batch-load all relevant mappings in a single query
        all_account_types = self.mapped("account_id.account_type")
        mapping_records = Mapping.search([
            ("account_type", "in", all_account_types),
            ("active", "=", True),
        ])
        mapping_dict = {m.account_type: m.financial_section for m in mapping_records}

        for line in self:
            account_type = line.account_id.account_type if line.account_id else False
            line.sgc_dfr_financial_section = mapping_dict.get(account_type, "other")