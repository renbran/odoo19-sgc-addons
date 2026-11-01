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
        cls.client.owner_user_id = cls.portal_user
        cls.client.link_owner_login = "sgc-portal-test"
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

        # One workspace: the card's target goes straight to the upload page.
        response = self.url_open("/my/accounting", allow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response.headers["Location"].endswith("/my/accounting/portal-client"))

        response = self.url_open("/my/accounting/portal-client")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SGC Portal Company", response.text)
        self.assertIn("Upload buckets", response.text)
        self.assertIn("Purchase Bills", response.text)
        self.assertIn("Download sample CSV", response.text)
        self.assertIn("Upload a document", response.text)
        self.assertIn('href="/my/home"', response.text)
        self.assertNotIn("All accounting workspaces", response.text)

        response = self.url_open("/my/home")
        self.assertEqual(response.status_code, 200)
        self.assertIn('href="/my/accounting"', response.text)
        self.assertIn("Upload your accounting entries and documents", response.text)

        # Several workspaces owned by this login: the list is shown, with a way
        # back to it. One of the same company without this owner stays hidden.
        self.env["sgc.accounting.client"].create(
            [
                {
                    "name": "SGC Portal Client Two",
                    "client_code": "portal-client-two",
                    "partner_id": self.portal_partner.id,
                    "owner_user_id": self.portal_user.id,
                    "status": "active",
                },
                {
                    "name": "SGC Portal Client Three",
                    "client_code": "portal-client-three",
                    "partner_id": self.portal_partner.id,
                    "status": "active",
                },
            ]
        )
        response = self.url_open("/my/accounting")
        self.assertEqual(response.status_code, 200)
        self.assertIn("SGC Portal Client Two", response.text)
        self.assertNotIn("SGC Portal Client Three", response.text)
        self.assertIn("Open workspace", response.text)
        response = self.url_open("/my/accounting/portal-client")
        self.assertIn("All accounting workspaces", response.text)

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

    def test_only_the_owner_opens_the_workspace(self):
        colleague = self.env["res.partner"].create(
            {"name": "Colleague", "parent_id": self.portal_partner.id}
        )
        self.env["res.users"].create(
            {
                "name": "Colleague",
                "login": "sgc-portal-colleague",
                "password": "sgc-portal-colleague",
                "partner_id": colleague.id,
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        self.env["res.users"].create(
            {
                "name": "Agency Staff",
                "login": "sgc-agency-staff",
                "password": "sgc-agency-staff",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("sgc_accounting_clients.group_sgc_accounting_manager").id),
                ],
            }
        )
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "other",
                "filename": "note.pdf",
                "file": "JVBERi0xLjQ=",
            }
        )
        for login in ("sgc-portal-colleague", "sgc-agency-staff"):
            self.authenticate(login, login)
            for url in (
                "/my/accounting/portal-client",
                "/my/accounting/portal-client/document/%s" % upload.id,
                "/my/accounting/upload/%s/download" % upload.id,
            ):
                self.assertEqual(self.url_open(url).status_code, 404, (login, url))
        self.authenticate("sgc-portal-test", "sgc-portal-test")
        self.assertEqual(
            self.url_open("/my/accounting/portal-client/document/%s" % upload.id).status_code, 200
        )
        # Another subscription's document, even through this owner's workspace.
        other_partner = self.env["res.partner"].create({"name": "Other Subscriber"})
        other_owner = self.env["res.users"].create(
            {
                "name": "Other Subscriber",
                "login": "sgc-portal-other",
                "partner_id": other_partner.id,
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        other = self.env["sgc.accounting.client"].create(
            {"name": "Other Subscriber", "client_code": "portal-other", "partner_id": other_partner.id,
             "owner_user_id": other_owner.id}
        )
        theirs = self.env["sgc.accounting.upload"].create(
            {"client_id": other.id, "doc_type": "chart_of_accounts", "filename": "coa.csv", "file": "QQ=="}
        )
        for url in (
            "/my/accounting/portal-other",
            "/my/accounting/portal-client/document/%s" % theirs.id,
            "/my/accounting/upload/%s/download" % theirs.id,
        ):
            self.assertEqual(self.url_open(url).status_code, 404, url)
        for url in (
            "/my/accounting/portal-client/document/%s/approve" % theirs.id,
            "/my/accounting/portal-other/document/%s/approve" % theirs.id,
        ):
            response = self.url_open(url, data={"csrf_token": Request.csrf_token(self)}, allow_redirects=False)
            self.assertEqual(response.status_code, 404, url)
        self.assertEqual(theirs.booking_state, "approval")

    def test_owner_reviews_and_approves_chart_of_accounts(self):
        from odoo.addons.sgc_accounting_clients.models.accounting_bucket import sample_csv

        response = self._post_upload(
            "coa.csv", sample_csv("chart_of_accounts"), "text/csv", doc_type="chart_of_accounts"
        )
        self.assertEqual(response.status_code, 303)
        upload = self.env["sgc.accounting.upload"].search(
            [("client_id", "=", self.client.id), ("doc_type", "=", "chart_of_accounts")], limit=1
        )
        self.assertEqual(upload.booking_state, "approval")
        page = self.url_open("/my/accounting/portal-client/document/%s" % upload.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn("Approve and apply to my database", page.text)
        self.assertIn(upload.sha256, page.text)
        # A file other than the one shown is not approved.
        response = self.url_open(
            "/my/accounting/portal-client/document/%s/approve" % upload.id,
            data={"csrf_token": Request.csrf_token(self), "sha256": "0" * 64},
            allow_redirects=False,
        )
        self.assertIn("message=not_approved", response.headers["Location"])
        self.assertIn("611010", page.text)
        listing = self.url_open("/my/accounting/portal-client")
        self.assertIn("/my/accounting/portal-client/document/%s" % upload.id, listing.text)
        response = self.url_open(
            "/my/accounting/portal-client/document/%s/approve" % upload.id,
            data={"csrf_token": Request.csrf_token(self), "sha256": upload.sha256},
            allow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("message=approved", response.headers["Location"])
        upload.invalidate_recordset()
        self.assertEqual(upload.booking_state, "pending")
        self.assertIn("approved", upload.log_ids.mapped("event"))
        # Approving twice does nothing.
        response = self.url_open(
            "/my/accounting/portal-client/document/%s/approve" % upload.id,
            data={"csrf_token": Request.csrf_token(self), "sha256": upload.sha256},
            allow_redirects=False,
        )
        self.assertIn("message=not_approved", response.headers["Location"])

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

    def test_portal_agent_callback_rejects_bad_signature(self):
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "callback-bad-signature.pdf",
                "file": b"JVBERi0xLjQ=",
                "state": "validated",
            }
        )
        upload.action_queue_agent()
        run = upload.agent_run_ids
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_accounting_clients.agent_callback_secret",
            "callback-test-secret",
        )
        body = json.dumps(
            {"run_id": run.run_id, "state": "completed", "matches": []}
        ).encode("utf-8")
        response = self.url_open(
            "/sgc/accounting/agent/callback",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-SGC-Signature": "not-a-valid-signature",
                "X-SGC-Timestamp": str(int(time.time())),
            },
            method="POST",
        )
        self.assertEqual(response.status_code, 403)
        run.invalidate_recordset()
        self.assertEqual(run.state, "queued")

    def test_portal_agent_callback_rejects_expired_timestamp(self):
        upload = self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "callback-expired.pdf",
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
        timestamp = str(int(time.time()) - 3600)
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
        self.assertEqual(response.status_code, 403)
        run.invalidate_recordset()
        self.assertEqual(run.state, "queued")
