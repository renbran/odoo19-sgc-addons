# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import common

class TestConstructionAccounting(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestConstructionAccounting, cls).setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Vendor'})
        cls.project = cls.env['construction.project'].create({
            'name': 'Test Project',
            'client_id': cls.partner.id,
        })
        cls.product = cls.env.ref('sgc_construction_management.product_construction_progress_billing')
        cls.retention_product = cls.env.ref('sgc_construction_management.product_retention_deduction')

    def test_01_project_analytic_account(self):
        """Test that analytic account is created for project"""
        self.assertTrue(self.project.analytic_account_id, "Analytic account should be created")
        self.assertEqual(self.project.analytic_account_id.name, self.project.name)

    def test_02_ra_billing_invoice(self):
        """Test RA Billing invoice creation"""
        ra_billing = self.env['construction.ra.billing'].create({
            'name': 'RA 1',
            'project_id': self.project.id,
        })
        self.assertEqual(ra_billing.ra_number, 1)

        self.env['construction.ra.billing.line'].create({
            'billing_id': ra_billing.id,
            'boq_line_description': 'Test Line',
            'qty_current': 10,
            'unit_rate': 100,
        })
        ra_billing.action_approve()
        ra_billing.action_create_invoice()

        self.assertTrue(ra_billing.move_id, "Invoice should be created")
        self.assertEqual(ra_billing.move_id.move_type, 'out_invoice')
        self.assertEqual(ra_billing.state, 'invoice_created')

        # Check lines
        work_line = ra_billing.move_id.invoice_line_ids.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(work_line.price_unit, 1000.0)

        # Check analytic distribution
        self.assertIn(str(self.project.analytic_account_id.id), work_line.analytic_distribution)

    def test_03_expense_bill(self):
        """Test Expense vendor bill creation"""
        account = self.env['account.account'].create({
            'name': 'Test Expense Account',
            'code': 'TEST_EXP',
            'account_type': 'expense',
        })
        category = self.env['construction.expense.category'].create({
            'name': 'Test Category',
            'property_account_expense_id': account.id,
        })
        expense = self.env['construction.expense'].create({
            'name': 'Test Expense',
            'project_id': self.project.id,
            'partner_id': self.vendor.id,
            'amount': 500.0,
            'category_id': category.id,
        })
        expense.action_approve()
        expense.action_create_bill()

        self.assertTrue(expense.move_id, "Vendor bill should be created")
        self.assertEqual(expense.move_id.move_type, 'in_invoice')
        self.assertEqual(expense.state, 'bill_created')

    def test_04_project_financials(self):
        """Test project financial KPIs from accounting"""
        ra_billing = self.env['construction.ra.billing'].create({
            'name': 'RA 1',
            'project_id': self.project.id,
        })
        self.env['construction.ra.billing.line'].create({
            'billing_id': ra_billing.id,
            'boq_line_description': 'Test Line',
            'qty_current': 10,
            'unit_rate': 100,
        })
        ra_billing.action_approve()
        ra_billing.action_create_invoice()
        ra_billing.move_id.action_post()

        self.project._compute_financials()
        self.assertEqual(self.project.total_billed, 1000.0)

    def test_05_boq_qty_constraint(self):
        """Test BOQ quantity constraint in RA Billing"""
        boq = self.env['construction.boq'].create({
            'name': 'Test BOQ',
            'project_id': self.project.id,
        })
        boq_line = self.env['construction.boq.line'].create({
            'boq_id': boq.id,
            'description': 'Item 1',
            'qty': 10,
            'unit_rate': 100,
        })
        boq.action_approve()

        ra_billing = self.env['construction.ra.billing'].create({
            'name': 'RA 1',
            'project_id': self.project.id,
        })
        ra_line = self.env['construction.ra.billing.line'].create({
            'billing_id': ra_billing.id,
            'boq_line_id': boq_line.id,
            'qty_current': 15, # Greater than BOQ qty
        })

        with self.assertRaises(ValidationError):
            ra_line._check_qty_limit()

    def test_06_quality_gating(self):
        """Test quality gating in RA Billing"""
        ra_billing = self.env['construction.ra.billing'].create({
            'name': 'RA 1',
            'project_id': self.project.id,
        })
        self.env['construction.quality.check'].create({
            'name': 'Failed Check',
            'project_id': self.project.id,
            'state': 'failed',
        })
        ra_billing.action_approve()
        with self.assertRaises(ValidationError):
            ra_billing.action_create_invoice()

    def _make_approved_ra_billing(self):
        ra_billing = self.env['construction.ra.billing'].create({
            'name': 'RA 1',
            'project_id': self.project.id,
        })
        self.env['construction.ra.billing.line'].create({
            'billing_id': ra_billing.id,
            'boq_line_description': 'Test Line',
            'qty_current': 10,
            'unit_rate': 100,
        })
        ra_billing.action_approve()
        return ra_billing

    def test_07_ra_billing_recreate_after_invoice_cancelled(self):
        """A cancelled invoice must revert the billing and allow re-invoicing."""
        ra_billing = self._make_approved_ra_billing()
        ra_billing.action_create_invoice()
        first_move = ra_billing.move_id
        self.assertEqual(ra_billing.state, 'invoice_created')

        # Cancel the underlying invoice (the scenario from the bug report).
        first_move.button_cancel()
        self.assertEqual(first_move.state, 'cancel')
        # Automated on-change: state drops back to 'approved' so it is not stuck.
        self.assertEqual(ra_billing.state, 'approved')

        # Re-creating the invoice must now work and link a brand-new move.
        ra_billing.action_create_invoice()
        self.assertEqual(ra_billing.state, 'invoice_created')
        self.assertNotEqual(ra_billing.move_id, first_move)
        self.assertNotEqual(ra_billing.move_id.state, 'cancel')

    def test_08_ra_billing_action_cancel(self):
        """The Cancel button cancels the invoice; the billing reverts to approved
        and keeps the invoice linked so it can be reopened."""
        ra_billing = self._make_approved_ra_billing()
        ra_billing.action_create_invoice()
        move = ra_billing.move_id

        ra_billing.action_cancel()
        self.assertEqual(move.state, 'cancel')
        self.assertEqual(ra_billing.state, 'approved')
        self.assertEqual(ra_billing.move_id, move, "Cancelled invoice stays linked")

    def test_09_ra_billing_reopen_after_accidental_cancel(self):
        """An accidental cancel can be undone with Reopen Invoice."""
        ra_billing = self._make_approved_ra_billing()
        ra_billing.action_create_invoice()
        move = ra_billing.move_id

        ra_billing.action_cancel()
        self.assertEqual(ra_billing.state, 'approved')

        ra_billing.action_reopen_invoice()
        self.assertEqual(move.state, 'draft')
        self.assertEqual(ra_billing.move_id, move, "Same invoice is restored")
        self.assertEqual(ra_billing.state, 'invoice_created')
