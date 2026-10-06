# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import ValidationError

class TestConstructionOperations(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestConstructionOperations, cls).setUpClass()
        cls.project = cls.env['construction.project'].create({
            'name': 'Op Test Project',
        })

    def test_01_wbs_recursion(self):
        """Test WBS recursion constraint"""
        wbs1 = self.env['construction.wbs'].create({
            'name': 'Phase 1',
            'project_id': self.project.id,
        })
        wbs2 = self.env['construction.wbs'].create({
            'name': 'Phase 2',
            'project_id': self.project.id,
            'parent_id': wbs1.id,
        })
        with self.assertRaises(ValidationError):
            wbs1.parent_id = wbs2.id

    def test_02_material_requisition_qty(self):
        """Test material requisition quantity constraints"""
        product = self.env['product.product'].create({
            'name': 'Cement',
            'type': 'consu',
        })
        req = self.env['construction.material.requisition'].create({
            'name': 'Req 1',
            'project_id': self.project.id,
        })
        line = self.env['construction.material.requisition.line'].create({
            'requisition_id': req.id,
            'product_id': product.id,
            'qty_requested': 100,
        })

        # Approved > Requested
        with self.assertRaises(ValidationError):
            line.qty_approved = 150
            line._check_quantities()

        # Received > Approved
        line.qty_approved = 90
        with self.assertRaises(ValidationError):
            line.qty_received = 95
            line._check_quantities()
