# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import os
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

CSV_INVOICE = (
    "Invoice Number,Invoice Date,Customer Name,Currency,Description,Quantity,"
    "Unit Price,Tax Rate,Tax Amount,Total,Due Date\n"
    "INV-2026-0042,2026-10-20,Example Customer LLC,AED,Consulting services,"
    "2,1500,5,150,3150,2026-11-19\n"
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


@tagged("post_install", "-at_install")
class TestSgcAccountingAgentChat(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Chat Agent Client"})
        cls.client = cls.env["sgc.accounting.client"].create(
            {
                "name": "Chat Agent Client",
                "client_code": "chat-client",
                "partner_id": cls.partner.id,
                "legal_name": "Chat Agent Client FZ-LLC",
                "trn": "100000000000003",
                "base_url": "https://demo.sgctech.ai",
                "db_name": "demo_presentation",
            }
        )
        cls.company = cls.env["sgc.accounting.company"].create(
            {
                "client_id": cls.client.id,
                "odoo_company_id": 1,
                "name": "Chat Agent Company",
                "trn": "100000000000003",
                "is_default": True,
            }
        )
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.params.set_param("sgc_accounting_clients.agent_endpoint", "")
        cls.params.set_param("sgc_accounting_clients.agent_transport", "event")
        cls.params.set_param("sgc_accounting_clients.agent_chat_secret", "")
        cls.params.set_param("sgc_accounting_clients.agent_chat_user_id", "2")
        cls.params.set_param("sgc_accounting_clients.agent_callback_secret", "")

    def _upload(self):
        return self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": "customer_invoices",
                "filename": "invoice.csv",
                "file": base64.b64encode(CSV_INVOICE.encode("utf-8")),
                "state": "validated",
            }
        )

    def _run(self):
        upload = self._upload()
        upload.action_queue_agent()
        return upload.agent_run_ids

    def _enable_chat(self):
        self.params.set_param(
            "sgc_accounting_clients.agent_endpoint", "http://orchestrator:8088/chat"
        )
        self.params.set_param("sgc_accounting_clients.agent_transport", "chat")
        self.params.set_param("sgc_accounting_clients.agent_chat_secret", "chat-secret")

    def test_chat_transport_completes_with_verified_match(self):
        self._enable_chat()
        reply = {
            "reply": json.dumps(
                {
                    "state": "completed",
                    "matches": [
                        {
                            "reference": "INV-2026-0042",
                            "counterparty": "Example Customer LLC",
                            "total": 3150.0,
                            "currency": "AED",
                            "confidence": 0.95,
                            "trn": "100000000000003",
                        }
                    ],
                    "extraction": {"invoice_number": "INV-2026-0042", "total": 3150.0},
                    "error": "",
                }
            )
        }
        with patch("requests.post", return_value=FakeResponse(reply)) as post:
            run = self._run()
            run.action_dispatch()
        run.invalidate_recordset()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(run.transport, "chat")
        self.assertEqual(run.state, "completed")
        self.assertEqual(run.response_code, 200)
        self.assertEqual(len(run.matches), 1)
        self.assertEqual(run.matches[0]["reference"], "INV-2026-0042")
        self.assertEqual(run.extraction["invoice_number"], "INV-2026-0042")
        self.assertFalse(run.review_required)
        self.assertFalse(run.last_error)
        request = post.call_args.kwargs
        self.assertTrue(request["headers"]["Authorization"].startswith("Bearer "))
        self.assertIn("Example Customer LLC", request["json"]["prompt"])
        self.assertIn("3150.0", request["json"]["prompt"])

    def test_chat_transport_flags_review_when_trn_is_missing(self):
        self._enable_chat()
        reply = {
            "reply": json.dumps(
                {
                    "state": "completed",
                    "matches": [
                        {
                            "reference": "INV-2026-0042",
                            "counterparty": "Example Customer LLC",
                            "total": 3150.0,
                            "currency": "AED",
                            "confidence": 0.95,
                        }
                    ],
                    "extraction": {"total": 3150.0},
                    "error": "",
                }
            )
        }
        with patch("requests.post", return_value=FakeResponse(reply)):
            run = self._run()
            run.action_dispatch()
        run.invalidate_recordset()
        self.assertEqual(run.state, "completed")
        self.assertTrue(run.review_required)

    def test_chat_transport_fails_closed_on_checksum_mismatch(self):
        self._enable_chat()
        reply = {
            "reply": json.dumps(
                {
                    "state": "completed",
                    "matches": [
                        {
                            "reference": "INV-2026-0042",
                            "counterparty": "Example Customer LLC",
                            "total": 9999.0,
                            "currency": "AED",
                            "confidence": 0.9,
                        }
                    ],
                    "extraction": {},
                    "error": "",
                }
            )
        }
        with patch("requests.post", return_value=FakeResponse(reply)):
            run = self._run()
            sent = run._send("http://orchestrator:8088/chat")
        run.invalidate_recordset()
        self.assertFalse(sent)
        self.assertEqual(run.state, "failed")
        self.assertIn("Checksum mismatch", run.last_error)
        self.assertFalse(run.matches)

    def test_chat_transport_rejects_malformed_reply(self):
        self._enable_chat()
        reply = {"reply": "I could not read that document."}
        with patch("requests.post", return_value=FakeResponse(reply)):
            run = self._run()
            sent = run._send("http://orchestrator:8088/chat")
        run.invalidate_recordset()
        self.assertFalse(sent)
        self.assertEqual(run.state, "queued")
        self.assertIn("JSON", run.last_error)
        self.assertEqual(run.attempts, 1)

    def test_chat_transport_rejects_unsupported_state(self):
        self._enable_chat()
        reply = {"reply": json.dumps({"state": "posted", "matches": []})}
        with patch("requests.post", return_value=FakeResponse(reply)):
            run = self._run()
            sent = run._send("http://orchestrator:8088/chat")
        run.invalidate_recordset()
        self.assertFalse(sent)
        self.assertEqual(run.state, "failed")
        self.assertIn("unsupported state", run.last_error)

    def test_dispatch_button_reports_the_agent_error(self):
        self._enable_chat()
        reply = {"reply": json.dumps({"state": "posted", "matches": []})}
        with patch("requests.post", return_value=FakeResponse(reply)):
            run = self._run()
            with self.assertRaises(Exception):
                run.action_dispatch()

    def test_chat_transport_requires_secret(self):
        self._enable_chat()
        self.params.set_param("sgc_accounting_clients.agent_chat_secret", "")
        run = self._run()
        with self.assertRaises(Exception):
            run.action_dispatch()

    def test_chat_transport_records_http_error(self):
        self._enable_chat()
        with patch(
            "requests.post",
            return_value=FakeResponse({"detail": "boom"}, status_code=500),
        ):
            run = self._run()
            sent = run._send("http://orchestrator:8088/chat")
        run.invalidate_recordset()
        self.assertFalse(sent)
        self.assertEqual(run.state, "queued")
        self.assertEqual(run.response_code, 500)
        self.assertIn("HTTP 500", run.last_error)

    def test_chat_token_is_signed_with_the_configured_secret(self):
        run = self._run()
        token = run._mint_chat_token("chat-secret", 2)
        header, claims, signature = token.split(".")
        expected = (
            base64.urlsafe_b64encode(
                hmac.new(
                    b"chat-secret",
                    ("%s.%s" % (header, claims)).encode("ascii"),
                    hashlib.sha256,
                ).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        self.assertEqual(signature, expected)
        payload = json.loads(
            base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4))
        )
        self.assertEqual(payload["sub"], "2")
        self.assertGreater(payload["exp"], payload["iat"])

    def test_event_transport_posts_the_event_payload(self):
        self.params.set_param(
            "sgc_accounting_clients.agent_endpoint", "http://agent.internal/hook"
        )
        self.params.set_param("sgc_accounting_clients.agent_transport", "event")
        with patch("requests.post", return_value=FakeResponse({"ok": True})) as post:
            run = self._run()
            run.action_dispatch()
        run.invalidate_recordset()
        self.assertEqual(post.call_count, 1)
        self.assertEqual(run.transport, "event")
        self.assertEqual(run.state, "dispatched")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["event"], "accounting.document.accepted")
        self.assertEqual(body["run_id"], run.run_id)
        self.assertEqual(
            post.call_args.kwargs["headers"]["X-SGC-Run-Id"], run.run_id
        )

    def test_authoritative_totals_reject_inconsistent_rows(self):
        run = self._run()
        headers = [
            "Invoice Number",
            "Quantity",
            "Unit Price",
            "Tax Amount",
            "Total",
        ]
        rows = [{"Quantity": "2", "Unit Price": "1500", "Tax Amount": "150", "Total": "3150"}]
        totals = run._authoritative_totals(headers, rows)
        self.assertEqual(totals["errors"], [])
        self.assertEqual(totals["total"], 3150.0)
        rows[0]["Total"] = "3000"
        broken = run._authoritative_totals(headers, rows)
        self.assertTrue(broken["errors"])
        self.assertIsNone(broken["total"])

    def test_workspace_booking_creates_a_draft_entry(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("sgc_accounting_clients.agent_workspace_enabled", "True")
        params.set_param(
            "sgc_accounting_clients.agent_workspace_url", "https://workspace.test"
        )
        params.set_param("sgc_accounting_clients.agent_workspace_db", "workspace")
        params.set_param("sgc_accounting_clients.agent_workspace_user_id", "72")
        handle, key_file = tempfile.mkstemp(prefix="sgc-agent-key-", suffix=".env")
        os.write(handle, b"SGC_AGENT_API_KEY=test-key\n")
        os.close(handle)
        self.addCleanup(os.unlink, key_file)
        params.set_param("sgc_accounting_clients.agent_workspace_key_file", key_file)

        created = {}

        class FakeServer:
            def __init__(self, *args, **kwargs):
                pass

            def execute_kw(self, db, uid, key, model, method, args=None, kwargs=None):
                if model == "res.partner" and method == "search_read":
                    return []
                if model == "res.partner" and method == "create":
                    return 55
                if model == "res.currency" and method == "search_read":
                    return [{"id": 1}]
                if model == "account.journal" and method == "search_read":
                    return [{"id": 9}]
                if model == "account.tax" and method == "search_read":
                    return [{"id": 4}]
                if model == "account.move" and method == "create":
                    created["values"] = args[0]
                    return 777
                raise AssertionError("unexpected call %s.%s" % (model, method))

        with patch("xmlrpc.client.ServerProxy", FakeServer):
            run = self._run()
            run._book_workspace_entry()
        run.invalidate_recordset()
        self.assertEqual(run.workspace_move_id, "777")
        values = created["values"]
        self.assertEqual(values["move_type"], "out_invoice")
        self.assertEqual(values["journal_id"], 9)
        self.assertEqual(values["partner_id"], 55)
        self.assertEqual(values["ref"], "INV-2026-0042")
        self.assertEqual(values["invoice_line_ids"][0][2]["price_unit"], 1500.0)
        self.assertEqual(values["invoice_line_ids"][0][2]["tax_ids"], [(6, 0, [4])])
        upload = run.upload_id
        self.assertIn("777", upload.odoo_move_ids)
