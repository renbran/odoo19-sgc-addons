# -*- coding: utf-8 -*-
import base64
import hashlib

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from ..models.accounting_bucket import (
    BUCKETS,
    sample_csv,
    validate_upload_format,
)


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
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "invoice.pdf",
                "file": base64.b64encode(payload),
            }
        )
        self.assertEqual(upload.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(upload.file_size, len(payload))
        self.assertIn("test-client/inbox/customer_invoices", upload.storage_path)

    def test_bucket_catalog_and_samples(self):
        self.assertEqual(len(BUCKETS), 9)
        self.assertIn("payments", {item["code"] for item in BUCKETS})
        sample = sample_csv("vendor_bills")
        self.assertTrue(sample.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"Bill Number", sample)
        self.assertIn(b"Example Supplier LLC", sample)

    def test_bucket_format_validation(self):
        good = (
            b"Invoice No,Date,Customer,Currency,Description,Quantity,"
            b"Unit Price,Tax Rate,Tax Amount,Total,Due Date\n"
            b"INV-1,2026-10-01,Example LLC,AED,Work,1,100,5,5,105,2026-10-31\n"
        )
        result = validate_upload_format("customer_invoices", "invoices.csv", good)
        self.assertIsNone(result["error"])
        self.assertEqual(result["row_count"], 1)
        self.assertIn("invoice number", result["headers"])

        missing = validate_upload_format(
            "customer_invoices", "invoices.csv", b"Invoice Number\nINV-1\n"
        )
        self.assertTrue(missing["missing"])
        self.assertIn("Invoice Date", missing["missing"])

        wrong_format = validate_upload_format(
            "master_data", "master.pdf", b"%PDF-1.4"
        )
        self.assertTrue(wrong_format["error"])

    def test_queue_agent(self):
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "queue.pdf",
                "file": base64.b64encode(b"%PDF-1.4 queue"),
            }
        )
        upload.action_queue_agent()
        self.assertEqual(upload.state, "validated")
        self.assertEqual(len(upload.agent_run_ids), 1)
        run = upload.agent_run_ids
        self.assertEqual(run.state, "queued")
        self.assertEqual(run.payload["bucket"]["code"], "customer_invoices")
        self.assertEqual(run.payload["match_target"]["url"], "https://demo.sgctech.ai")
        self.assertIn("timestamp_header", run.payload["callback"])

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
