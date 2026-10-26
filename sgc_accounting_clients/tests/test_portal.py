# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import time
import urllib.parse

from odoo import Command
from odoo.http import Request
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
        self.assertIn("Upload buckets", response.text)
        self.assertIn("Purchase Bills", response.text)
        self.assertIn("Download sample CSV", response.text)
        self.assertIn("Upload a document", response.text)

        response = self.url_open("/my")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Accounting", response.text)

    def _post_upload(self, filename, payload, mimetype, doc_type="customer_invoices"):
        self.authenticate("sgc-portal-test", "sgc-portal-test")
        return self.url_open(
            "/my/accounting/portal-client/upload",
            data={
                "csrf_token": Request.csrf_token(self),
                "doc_type": doc_type,
                "company_id": str(self.company.id),
            },
            files={"file": (filename, payload, mimetype)},
            allow_redirects=False,
        )

    def test_bucket_sample_download(self):
        self.authenticate("sgc-portal-test", "sgc-portal-test")
        response = self.url_open(
            "/my/accounting/portal-client/bucket/customer_invoices/sample"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("Content-Type", ""))
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"Invoice Number", response.content)
        self.assertIn(b"Example Customer LLC", response.content)

    def test_portal_upload(self):
        payload = b"%PDF-1.4 portal upload test"
        response = self._post_upload(
            "invoice.pdf", payload, "application/pdf"
        )
        self.assertEqual(response.status_code, 303)
        upload = self.env["sgc.accounting.upload"].search(
            [
                ("client_id", "=", self.client.id),
                ("filename", "=", "invoice.pdf"),
            ],
            limit=1,
        )
        self.assertTrue(upload)
        self.assertEqual(upload.sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(upload.state, "validated")
        run = upload.agent_run_ids
        self.assertEqual(len(run), 1)
        self.assertEqual(run.state, "queued")
        self.assertEqual(run.payload["match_target"]["url"], "https://demo.sgctech.ai")
        self.assertEqual(
            run.payload["match_target"]["db_name"], "demo_presentation"
        )
        self.assertIn("/sgc/accounting/agent/document/", run.payload["document"]["download_url"])

        path = urllib.parse.urlparse(run.payload["document"]["download_url"]).path
        query = urllib.parse.urlparse(run.payload["document"]["download_url"]).query
        download = self.url_open("%s?%s" % (path, query))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content, payload)

    def test_portal_rejects_bad_bucket_format(self):
        response = self._post_upload(
            "master.pdf",
            b"%PDF-1.4 not a spreadsheet",
            "application/pdf",
            doc_type="master_data",
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("message=bad_format", response.headers.get("Location", ""))
        upload = self.env["sgc.accounting.upload"].search(
            [("client_id", "=", self.client.id), ("filename", "=", "master.pdf")]
        )
        self.assertFalse(upload)

    def test_portal_rejects_missing_columns(self):
        response = self._post_upload(
            "invoice.csv",
            b"Invoice Number\nINV-1\n",
            "text/csv",
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("message=bad_format", response.headers.get("Location", ""))
        self.assertIn("missing=Invoice+Date", response.headers.get("Location", ""))

    def test_portal_agent_callback(self):
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "callback.pdf",
                "file": b"JVBERi0xLjQ=",
                "state": "validated",
            }
        )
        upload.action_queue_agent()
        run = upload.agent_run_ids
        secret = "callback-test-secret"
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_accounting_clients.agent_callback_secret", secret
        )
        body = json.dumps(
            {"run_id": run.run_id, "state": "completed", "matches": []}
        ).encode("utf-8")
        timestamp = str(int(time.time()))
        signature = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("utf-8") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        response = self.url_open(
            "/sgc/accounting/agent/callback",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-SGC-Signature": signature,
                "X-SGC-Timestamp": timestamp,
            },
            method="POST",
        )
        self.assertEqual(response.status_code, 200)
        run.invalidate_recordset()
        self.assertEqual(run.state, "completed")
        self.assertEqual(response.json()["state"], "completed")
