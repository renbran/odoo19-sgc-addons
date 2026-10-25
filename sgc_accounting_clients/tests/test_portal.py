# -*- coding: utf-8 -*-
from odoo import Command
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSgcAccountingPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal_partner = cls.env["res.partner"].create(
            {
                "name": "SGC Portal Client",
                "company_type": "company",
                "email": "portal-client@example.com",
                "customer_rank": 1,
            }
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "SGC Portal User",
                "login": "sgc-portal-test",
                "password": "sgc-portal-test",
                "partner_id": cls.portal_partner.id,
                "group_ids": [
                    Command.set([cls.env.ref("base.group_portal").id])
                ],
            }
        )
        cls.client = cls.env["sgc.accounting.client"].create(
            {
                "name": "SGC Portal Client",
                "client_code": "portal-client",
                "partner_id": cls.portal_partner.id,
                "legal_name": "SGC Portal Client FZ-LLC",
                "trn": "100000000000003",
                "base_url": "https://demo.sgctech.ai",
                "db_name": "demo_presentation",
                "status": "active",
            }
        )
        cls.company = cls.env["sgc.accounting.company"].create(
            {
                "client_id": cls.client.id,
                "odoo_company_id": 1,
                "name": "SGC Portal Company",
                "trn": "100000000000003",
                "is_default": True,
            }
        )

    def test_portal_pages(self):
        self.authenticate("sgc-portal-test", "sgc-portal-test")

        response = self.url_open("/my/accounting")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SGC Portal Client", response.text)
        self.assertIn("Open workspace", response.text)

        response = self.url_open("/my/accounting/portal-client")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SGC Portal Company", response.text)
        self.assertIn("Upload a document", response.text)

        response = self.url_open("/my")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Accounting", response.text)
