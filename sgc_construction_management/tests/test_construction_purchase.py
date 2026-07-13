# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import common


class TestConstructionPurchase(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Supplier'})
        cls.project = cls.env['construction.project'].create({
            'name': 'Purchase Test Project',
            'client_id': cls.partner.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Portland Cement',
            'type': 'consu',
            'standard_price': 25.0,
        })

    def _make_approved_requisition(self):
        req = self.env['construction.material.requisition'].create({
            'name': 'REQ Cement',
            'project_id': self.project.id,
        })
        self.env['construction.material.requisition.line'].create({
            'requisition_id': req.id,
            'product_id': self.product.id,
            'description': 'Cement bags',
            'qty_requested': 100,
            'qty_approved': 100,
            'unit_price': 25.0,
        })
        req.action_submit()
        req.action_approve()
        return req

    def test_01_create_purchase_from_requisition(self):
        """An approved requisition spawns a linked Purchase Order with its lines."""
        req = self._make_approved_requisition()
        action = req.action_create_purchase()
        po = self.env['construction.purchase.order'].browse(action['res_id'])

        self.assertTrue(po, "Purchase Order should be created")
        self.assertEqual(po.requisition_id, req)
        self.assertEqual(po.project_id, self.project)
        self.assertEqual(len(po.line_ids), 1)
        self.assertEqual(po.line_ids.quantity, 100)
        self.assertEqual(po.state, 'rfq')
        self.assertEqual(req.purchase_order_count, 1)

    def test_02_confirm_requires_vendor(self):
        """An LPO cannot be confirmed without a vendor."""
        req = self._make_approved_requisition()
        po = self.env['construction.purchase.order'].browse(req.action_create_purchase()['res_id'])
        with self.assertRaises(ValidationError):
            po.action_confirm()
        po.vendor_id = self.vendor
        po.action_confirm()
        self.assertEqual(po.state, 'confirmed')

    def test_03_create_bill_e2e(self):
        """Confirmed PO -> vendor bill in Accounting with project analytic distribution."""
        req = self._make_approved_requisition()
        po = self.env['construction.purchase.order'].browse(req.action_create_purchase()['res_id'])
        po.vendor_id = self.vendor
        po.action_confirm()
        po.action_create_bill()

        self.assertTrue(po.move_id, "Vendor bill should be created")
        self.assertEqual(po.move_id.move_type, 'in_invoice')
        self.assertEqual(po.move_id.partner_id, self.vendor)
        self.assertEqual(po.state, 'bill_created')

        line = po.move_id.invoice_line_ids.filtered(lambda l: l.product_id == self.product)
        self.assertTrue(line, "Bill should carry the product line")
        if self.project.analytic_account_id:
            self.assertIn(str(self.project.analytic_account_id.id), line.analytic_distribution)

    def test_04_cancel_and_reopen_bill(self):
        """Cancelling the bill reverts the PO; reopening restores the same bill."""
        req = self._make_approved_requisition()
        po = self.env['construction.purchase.order'].browse(req.action_create_purchase()['res_id'])
        po.vendor_id = self.vendor
        po.action_confirm()
        po.action_create_bill()
        move = po.move_id

        po.action_cancel_bill()
        self.assertEqual(move.state, 'cancel')
        self.assertEqual(po.state, 'confirmed')
        self.assertEqual(po.move_id, move, "Cancelled bill stays linked")

        po.action_reopen_bill()
        self.assertEqual(move.state, 'draft')
        self.assertEqual(po.state, 'bill_created')

    def test_05_recreate_bill_after_cancel(self):
        """After a cancelled bill the PO can produce a fresh bill."""
        req = self._make_approved_requisition()
        po = self.env['construction.purchase.order'].browse(req.action_create_purchase()['res_id'])
        po.vendor_id = self.vendor
        po.action_confirm()
        po.action_create_bill()
        first = po.move_id
        first.button_cancel()
        self.assertEqual(po.state, 'confirmed')

        po.action_create_bill()
        self.assertEqual(po.state, 'bill_created')
        self.assertNotEqual(po.move_id, first)
        self.assertNotEqual(po.move_id.state, 'cancel')
