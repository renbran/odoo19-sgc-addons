# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

import io

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tests import tagged

XLSX_MODEL_BY_REPORT_TYPE = {
    "balance_sheet": "report.sgc_dynamic_financial_report.sgc_balance_sheet_xlsx",
    "profit_loss": "report.sgc_dynamic_financial_report.sgc_profit_loss_xlsx",
    "cash_flow": "report.sgc_dynamic_financial_report.sgc_cash_flow_xlsx",
    "trial_balance": "report.sgc_dynamic_financial_report.sgc_trial_balance_xlsx",
    "general_ledger": "report.sgc_dynamic_financial_report.sgc_general_ledger_xlsx",
    "partner_ledger": "report.sgc_dynamic_financial_report.sgc_partner_ledger_xlsx",
    "aged_receivable": "report.sgc_dynamic_financial_report.sgc_aged_receivable_xlsx",
    "aged_payable": "report.sgc_dynamic_financial_report.sgc_aged_payable_xlsx",
    "tax_report": "report.sgc_dynamic_financial_report.sgc_tax_report_xlsx",
}


@tagged("post_install", "-at_install")
class TestSgcFinancialReportEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.wizard_model = cls.env["sgc.financial.report.wizard"]
        cls.engine_model = cls.env["sgc.financial.report.engine"]

        cls.partner = cls.env["res.partner"].create({"name": "SGC DFR Test Partner"})

        # Debit a receivable (asset), credit a payable (liability) - this
        # report doesn't roll period P&L into equity (no closing entries),
        # so an asset<->income seed would make "Assets == Liabilities +
        # Equity" legitimately false. Asset<->liability keeps that
        # invariant meaningfully testable while still giving the aged
        # receivable/partner ledger tests a receivable-side line to read.
        cls.payable_account = cls.env["account.account"].search([
            ("account_type", "=", "liability_payable"),
            ("company_ids", "in", cls.company.id),
        ], limit=1)
        cls.receivable_account = cls.env["account.account"].search([
            ("account_type", "=", "asset_receivable"),
            ("company_ids", "in", cls.company.id),
        ], limit=1)
        journal = cls.env["account.journal"].search([
            ("type", "=", "sale"),
            ("company_id", "=", cls.company.id),
        ], limit=1)

        move = cls.env["account.move"].create({
            "move_type": "entry",
            "journal_id": journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                (0, 0, {
                    "account_id": cls.receivable_account.id,
                    "partner_id": cls.partner.id,
                    "name": "SGC DFR test line (receivable)",
                    "debit": 1000.0,
                    "credit": 0.0,
                }),
                (0, 0, {
                    "account_id": cls.payable_account.id,
                    "partner_id": cls.partner.id,
                    "name": "SGC DFR test line (payable)",
                    "debit": 0.0,
                    "credit": 1000.0,
                }),
            ],
        })
        move.action_post()
        cls.move = move

    def _make_wizard(self, report_type, **extra):
        vals = {
            "report_type": report_type,
            "company_id": self.company.id,
            "date_from": fields.Date.today().replace(month=1, day=1),
            "date_to": fields.Date.today(),
        }
        vals.update(extra)
        return self.wizard_model.create(vals)

    # ── Account type mapping / post_init_hook ──────────────────────────

    def test_post_init_hook_created_mappings(self):
        """post_init_hook must have seeded global account-type mappings."""
        mappings = self.env["sgc.dfr.account.type"].search([])
        self.assertTrue(mappings, "post_init_hook should have seeded account type mappings")
        types = set(mappings.mapped("account_type"))
        self.assertIn("income", types)
        self.assertIn("asset_receivable", types)
        income_mapping = mappings.filtered(lambda m: m.account_type == "income")
        self.assertEqual(income_mapping.financial_section, "revenue")

    def test_post_init_hook_idempotent(self):
        """Running the hook twice must not create duplicate mappings."""
        from odoo.addons.sgc_dynamic_financial_report.hooks.post_init_hook import (
            post_init_hook_function,
        )
        before = self.env["sgc.dfr.account.type"].search_count([])
        post_init_hook_function(self.env)
        after = self.env["sgc.dfr.account.type"].search_count([])
        self.assertEqual(before, after, "running the hook twice must not duplicate mappings")

    # ── Wizard behaviour ─────────────────────────────────────────────

    def test_wizard_rejects_inverted_date_range(self):
        with self.assertRaises(ValidationError):
            self._make_wizard(
                "balance_sheet",
                date_from=fields.Date.today(),
                date_to=fields.Date.today().replace(year=fields.Date.today().year - 1),
            )

    # ── Every report type must generate HTML without error ─────────────

    def test_all_report_types_generate_html(self):
        for report_type, _label in self.wizard_model._fields["report_type"].selection:
            wizard = self._make_wizard(report_type)
            wizard.action_generate_report()
            self.assertTrue(wizard.result_html, f"{report_type} produced no HTML")
            self.assertEqual(wizard.state, "computed")

    # ── Financial correctness invariants ────────────────────────────────

    def test_balance_sheet_assets_equal_liabilities_plus_equity(self):
        wizard = self._make_wizard("balance_sheet")
        result = self.engine_model._generate_report(wizard)
        totals = result["data"]["totals"]
        self.assertAlmostEqual(
            totals["assets"], totals["liabilities_equity"], places=2,
            msg="Balance Sheet must balance: Assets == Liabilities + Equity",
        )

    def test_trial_balance_debit_equals_credit(self):
        wizard = self._make_wizard("trial_balance")
        result = self.engine_model._generate_report(wizard)
        totals = result["data"]["totals"]
        self.assertAlmostEqual(totals["debit"], totals["credit"], places=2)

    def test_aged_receivable_bucket_totals_match_balance(self):
        wizard = self._make_wizard("aged_receivable")
        result = self.engine_model._generate_report(wizard)
        for row in result["data"]["rows"]:
            bucket_sum = sum(row[b["label"]] for b in result["data"]["buckets"])
            self.assertAlmostEqual(
                bucket_sum, row["total_balance"], places=2,
                msg="Aging buckets for a partner must sum to their total balance",
            )

    # ── XLSX export for all 9 report types ──────────────────────────────

    def test_all_xlsx_reports_generate(self):
        try:
            import xlsxwriter
        except ImportError:
            self.skipTest("xlsxwriter not installed")

        for report_type, model_name in XLSX_MODEL_BY_REPORT_TYPE.items():
            wizard = self._make_wizard(report_type)
            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            self.env[model_name].generate_xlsx_report(workbook, {}, wizard)
            workbook.close()
            self.assertGreater(
                len(output.getvalue()), 0,
                f"{report_type} XLSX export produced an empty file",
            )
