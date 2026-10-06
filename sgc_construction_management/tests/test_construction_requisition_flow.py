# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError
from odoo.tests import common

class TestConstructionRequisitionFlow(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Test Client'})
        cls.vendor = cls.env['res.partner'].create({'name': 'Test Supplier'})
        cls.project = cls.env['construction.project'].create({
            'name': 'Requisition Flow Project',
            'client_id': cls.partner.id,
        })
        cls.wbs = cls.env['construction.wbs'].create({
            'name': 'Phase 1: Excavation',
            'project_id': cls.project.id,
        })
        cls.work_order = cls.env['construction.work.order'].create({
            'name': 'Excavation Work',
            'project_id': cls.project.id,
            'wbs_id': cls.wbs.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Safety Gear',
            'type': 'consu',
            'standard_price': 50.0,
        })

    def test_01_requisition_wbs_integration(self):
        """Requisition should pick up WBS from Work Order and pass it to PO."""
        requisition = self.env['construction.material.requisition'].create({
            'name': 'REQ Safety',
            'project_id': self.project.id,
            'work_order_id': self.work_order.id,
        })
        # Simulate onchange
        requisition._onchange_work_order_id()
        self.assertEqual(requisition.wbs_id, self.wbs, "Requisition should inherit WBS from Work Order")

        self.env['construction.material.requisition.line'].create({
            'requisition_id': requisition.id,
            'product_id': self.product.id,
            'qty_requested': 10,
            'qty_approved': 10,
            'unit_price': 50.0,
        })
        requisition.action_submit()
        requisition.action_approve()

        action = requisition.action_create_purchase()
        po = self.env['construction.purchase.order'].browse(action['res_id'])
        self.assertEqual(po.wbs_id, self.wbs, "Purchase Order should inherit WBS from Requisition")

    def test_02_billing_received_constraint(self):
        """Enforce that items must be received before billing."""
        po = self.env['construction.purchase.order'].create({
            'name': 'LPO Safety',
            'project_id': self.project.id,
            'vendor_id': self.vendor.id,
        })
        self.env['construction.purchase.order.line'].create({
            'order_id': po.id,
            'product_id': self.product.id,
            'quantity': 10,
            'price_unit': 50.0,
        })
        po.action_confirm()

        # Try to create bill while in 'confirmed' state
        with self.assertRaises(ValidationError, msg="Should not allow billing before reception"):
            po.action_create_bill()

        po.action_receive()
        self.assertEqual(po.state, 'received')

        # Now it should work
        po.action_create_bill()
        self.assertTrue(po.move_id, "Bill should be created after reception")
