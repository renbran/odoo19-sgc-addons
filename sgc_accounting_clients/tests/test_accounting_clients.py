# -*- coding: utf-8 -*-
import base64
import hashlib

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSgcAccountingClients(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Accounting Client"}
        )
        cls.client = cls.env["sgc.accounting.client"].create(
            {
                "name": "Test Accounting Client",
                "client_code": "test-client",
                "partner_id": cls.partner.id,
                "legal_name": "Test Accounting Client FZ-LLC",
                "trn": "100000000000003",
                "base_url": "https://demo.sgctech.ai",
                "db_name": "demo_presentation",
            }
        )
        cls.company = cls.env["sgc.accounting.company"].create(
            {
                "client_id": cls.client.id,
                "odoo_company_id": 1,
                "name": "Test Accounting Client FZ-LLC",
                "trn": "100000000000003",
                "is_default": True,
            }
        )

    def test_client_code_validation(self):
        with self.assertRaises(ValidationError):
            self.env["sgc.accounting.client"].create(
                {
                    "name": "Bad Code",
                    "client_code": "Bad Code",
                    "partner_id": self.partner.id,
                }
            )
        with self.assertRaises(ValidationError):
            self.env["sgc.accounting.client"].create(
                {
                    "name": "Reserved",
                    "client_code": "app",
                    "partner_id": self.partner.id,
                }
            )

    def test_trn_validation(self):
        with self.assertRaises(ValidationError):
            self.env["sgc.accounting.company"].create(
                {
                    "client_id": self.client.id,
                    "odoo_company_id": 2,
                    "name": "Bad TRN",
                    "trn": "123",
                }
            )

    def test_upload_metadata(self):
        payload = b"%PDF-1.4 test"
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "invoice.pdf",
                "file": base64.b64encode(payload),
            }
        )
        self.assertEqual(upload.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(upload.file_size, len(payload))
        self.assertIn("test-client/inbox/customer_invoices", upload.storage_path)

    def test_partner_accounting_context(self):
        self.assertEqual(self.partner.accounting_client_id, self.client)
        context = self.partner.accounting_context
        self.assertEqual(context["client_code"], "test-client")
        self.assertEqual(context["db_name"], "demo_presentation")
        self.assertEqual(context["companies"][0]["odoo_company_id"], 1)

    def test_provision_event(self):
        self.client.action_queue_provision()
        event = self.env["sgc.accounting.provision.event"].search(
            [("client_id", "=", self.client.id), ("event_type", "=", "provision")]
        )
        self.assertEqual(len(event), 1)
        self.assertEqual(event.state, "pending")
        self.assertEqual(self.client.status, "queued")
