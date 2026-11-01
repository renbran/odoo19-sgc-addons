# -*- coding: utf-8 -*-
import base64
import os
import tempfile
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.sgc_accounting_clients.models import accounting_client

INVOICES = (
    "Invoice Number,Invoice Date,Customer Name,Currency,Description,Quantity,"
    "Unit Price,Tax Rate,Tax Amount,Total,Due Date\n"
    "INV-1,2026-10-20,Known Customer,AED,Consulting,2,1500,5,150,3150,2026-11-19\n"
    "INV-1,2026-10-20,Known Customer,AED,Travel,1,200,5,10,210,2026-11-19\n"
    "INV-2,2026-10-21,New Customer,AED,Training,1,500,5,25,525,2026-11-20\n"
)
CREDIT_NOTES = (
    "Credit Note Number,Credit Note Date,Party Type,Party Name,Original Invoice,"
    "Currency,Description,Quantity,Unit Price,Tax Rate,Tax Amount,Total\n"
    "CN-1,2026-10-22,Supplier,Known Customer,BILL-9,AED,Return,1,100,5,5,105\n"
)
PAYMENTS = (
    "Payment Date,Direction,Reference,Party,Invoice Number,Amount,Currency,"
    "Bank Account,Payment Method\n"
    "2026-10-23,Outbound,PAY-1,Known Customer,BILL-9,1050.00,AED,Main Bank,Transfer\n"
    "2026-10-24,Sideways,PAY-2,Known Customer,,10,AED,Main Bank,Cash\n"
    "2026-10-25,Inbound,,Known Customer,,20,AED,Main Bank,Cash\n"
)
# Bill 1001 from two vendors is two bills; USD is not active in the client DB.
VENDOR_BILLS = (
    "Bill Number,Bill Date,Vendor Name,Currency,Description,Quantity,"
    "Unit Price,Tax Rate,Tax Amount,Total,Due Date\n"
    "1001,2026-10-20,Known Customer,AED,Rent,1,100,5,5,105,2026-11-19\n"
    "1001,2026-10-20,Other Vendor,AED,Paper,1,40,5,2,42,2026-11-19\n"
    "1002,2026-10-20,Other Vendor,USD,Toner,1,10,0,0,10,2026-11-19\n"
)


class FakeDatabase:
    """The client database behind XML-RPC: only search_read and create exist,
    so any attempt to post (action_post) fails the test."""

    def __init__(self):
        self.calls = []
        self.existing = {}

    def execute_kw(self, db, uid, key, model, method, args, kwargs):
        self.calls.append((db, uid, key, model, method, args, kwargs))
        if method == "create":
            return 100 + len(self.created())
        if method != "search_read":
            raise AssertionError("unexpected call %s.%s" % (model, method))
        domain = args[0]
        if model == "res.partner":
            known = ("name", "=ilike", "Known Customer") in domain
            return [{"id": 7}] if known else []
        if model == "res.currency":
            return [{"id": 130}] if ("name", "=ilike", "AED") in domain else []
        if model == "res.company":
            return [{"id": 3, "name": "Target Co"}]
        if model == "account.tax":
            return [{"id": 9, "company_id": [3, "Target Co"]}]
        if model == "account.journal":
            kind = domain[0][2]
            if kind == "sale":
                # The parent company's journal comes first; the target's wins.
                return [
                    {"id": 1, "company_id": [1, "Parent"]},
                    {"id": 2, "company_id": [3, "Target Co"]},
                ]
            if kind == "purchase":
                return [{"id": 4, "company_id": [3, "Target Co"]}]
            return [
                {"id": 5, "name": "Other Bank", "company_id": [3, "Target Co"]},
                {"id": 6, "name": "Main Bank", "company_id": [3, "Target Co"]},
            ]
        return self.existing.get(model, [])

    def created(self):
        return [call for call in self.calls if call[4] == "create"]


@tagged("post_install", "-at_install")
class TestSgcAccountingBooking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env["res.partner"].create({"name": "Booking Client"})
        cls.client = cls.env["sgc.accounting.client"].create(
            {
                "name": "Booking Client",
                "client_code": "booking-client",
                "partner_id": partner.id,
                "base_url": "https://client.test/",
                "db_name": "client_db",
                "api_user_id": 12,
            }
        )
        cls.company = cls.env["sgc.accounting.company"].create(
            {
                "client_id": cls.client.id,
                "odoo_company_id": 3,
                "name": "Target Co",
                "is_default": True,
            }
        )

    def setUp(self):
        super().setUp()
        secrets = tempfile.mkdtemp()
        self.key_file = os.path.join(secrets, "acc-booking-client.env")
        with open(self.key_file, "w", encoding="utf-8") as handle:
            handle.write("# client db key\nSGC_AGENT_API_KEY=client-key\n")
        self.addCleanup(os.unlink, self.key_file)
        patcher = patch.object(accounting_client, "SECRETS_DIR", secrets)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = FakeDatabase()

    def _upload(self, doc_type, content):
        return self.env["sgc.accounting.upload"].create(
            {
                "client_id": self.client.id,
                "accounting_company_id": self.company.id,
                "doc_type": doc_type,
                "filename": "%s.csv" % doc_type,
                "file": base64.b64encode(content.encode("utf-8")),
            }
        )

    def _book(self):
        with patch("xmlrpc.client.ServerProxy", return_value=self.db) as proxy:
            self.env["sgc.accounting.upload"]._cron_book_pending()
        return proxy

    def _events(self, upload):
        return upload.log_ids.sorted("id").mapped("event")

    def test_invoices_become_one_unposted_draft_per_document(self):
        upload = self._upload("customer_invoices", INVOICES)
        self.assertEqual(upload.booking_state, "pending")
        self.assertEqual(upload.target_db, "client_db")
        self.assertEqual(upload.target_base_url, "https://client.test")
        self.assertEqual(upload.target_company_ref, 3)
        self.assertEqual(upload.target_company_name, "Target Co")
        self.assertIn("client_db", upload.log_ids.message)

        proxy = self._book()

        self.assertEqual(upload.booking_state, "done")
        self.assertEqual(
            proxy.call_args.args[0], "https://client.test/xmlrpc/2/object"
        )
        for db, uid, key, _model, _method, _args, kwargs in self.db.calls:
            self.assertEqual((db, uid, key), ("client_db", 12, "client-key"))
            self.assertEqual(kwargs["context"], {"allowed_company_ids": [3]})
        created = self.db.created()
        self.assertEqual(len(created), 2)
        first, second = (call[5][0] for call in created)
        self.assertEqual(first["move_type"], "out_invoice")
        self.assertEqual(first["company_id"], 3)
        self.assertEqual(first["journal_id"], 2)
        self.assertEqual(first["ref"], "INV-1")
        self.assertEqual(first["invoice_date"], "2026-10-20")
        self.assertEqual(first["partner_id"], 7)
        self.assertEqual(first["currency_id"], 130)
        self.assertEqual(len(first["invoice_line_ids"]), 2)
        line = first["invoice_line_ids"][0][2]
        self.assertEqual((line["quantity"], line["price_unit"]), (2.0, 1500.0))
        self.assertEqual(line["tax_ids"], [(6, 0, [9])])
        self.assertEqual(second["ref"], "INV-2")
        self.assertNotIn("partner_id", second)
        self.assertIn("New Customer", second["narration"])
        self.assertIn("[SGC-DOC %s-1]" % upload.id, first["narration"])
        self.assertIn("[SGC-DOC %s-2]" % upload.id, second["narration"])
        self.assertEqual(self._events(upload), ["uploaded", "booked", "booked"])
        booked = upload.log_ids.filtered(lambda entry: entry.event == "booked")
        self.assertEqual(set(booked.mapped("record_model")), {"account.move"})
        self.assertEqual(set(booked.mapped("target_db")), {"client_db"})
        self.assertIn("3360.0", booked.filtered(lambda e: e.reference == "INV-1").message)

    def test_existing_reference_is_not_booked_twice(self):
        self.db.existing["account.move"] = [
            {"id": 55, "name": "INV/2026/0001", "state": "posted"}
        ]
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertFalse(self.db.created())
        self.assertEqual(self._events(upload), ["uploaded", "duplicate", "duplicate"])
        self.assertEqual(upload.booking_state, "done")
        duplicate_search = [
            call for call in self.db.calls
            if call[3] == "account.move" and call[4] == "search_read"
        ][0]
        self.assertIn(("company_id", "=", 3), duplicate_search[5][0])

    def test_supplier_credit_note_is_a_vendor_refund(self):
        self._upload("credit_notes", CREDIT_NOTES)
        self._book()
        values = self.db.created()[0][5][0]
        self.assertEqual(values["move_type"], "in_refund")
        self.assertEqual(values["journal_id"], 4)
        self.assertIn("BILL-9", values["narration"])

    def test_payments_one_draft_per_row_and_bad_rows_are_logged(self):
        upload = self._upload("payments", PAYMENTS)
        self._book()
        created = self.db.created()
        self.assertEqual(len(created), 2)
        self.assertEqual(created[0][3], "account.payment")
        self.assertEqual(created[1][5][0]["memo"], "SGC-%s-3" % upload.id)
        self.assertEqual(created[1][5][0]["payment_type"], "inbound")
        values = created[0][5][0]
        self.assertEqual(values["payment_type"], "outbound")
        self.assertEqual(values["partner_type"], "supplier")
        self.assertEqual(values["amount"], 1050.0)
        self.assertEqual(values["journal_id"], 6)
        self.assertEqual(values["memo"], "PAY-1")
        self.assertEqual(values["partner_id"], 7)
        self.assertEqual(
            self._events(upload), ["uploaded", "booked", "failed", "booked"]
        )
        self.assertEqual(upload.booking_state, "failed")

    def test_unlinked_client_waits_then_books(self):
        self.client.base_url = False
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "waiting")
        self.assertEqual(self._events(upload), ["uploaded", "waiting"])
        self.assertFalse(upload.target_base_url)
        self.client.base_url = "https://client.test"
        self._book()
        self.assertEqual(upload.target_base_url, "https://client.test")
        self.assertEqual(upload.booking_state, "done")
        self.assertEqual(len(self.db.created()), 2)

    def test_snapshot_does_not_follow_a_relinked_client(self):
        upload = self._upload("customer_invoices", INVOICES)
        self.client.db_name = "other_db"
        upload._snapshot_target()
        self.assertEqual(upload.target_db, "client_db")
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "failed")
        self.assertIn("other_db", upload.log_ids.sorted("id")[-1].message)

    def test_connection_needs_https_and_its_own_key_file(self):
        self.client.base_url = "http://client.test"
        self.assertIn("https", self.client._booking_connection()[1])
        self.client.base_url = "https://client.test"
        self.client.client_code = "other-client"
        conn, error = self.client._booking_connection()
        self.assertIsNone(conn)
        self.assertIn("cannot be read", error)

    def test_vendor_bills_are_keyed_by_vendor_and_number(self):
        upload = self._upload("vendor_bills", VENDOR_BILLS)
        self._book()
        created = [call[5][0] for call in self.db.created()]
        self.assertEqual(len(created), 2)
        self.assertEqual([values["ref"] for values in created], ["1001", "1001"])
        self.assertEqual(created[0]["partner_id"], 7)
        self.assertNotIn("partner_id", created[1])
        duplicate_search = [
            call[5][0] for call in self.db.calls
            if call[3] == "account.move" and call[4] == "search_read"
        ]
        self.assertIn(("partner_id", "=", 7), duplicate_search[0])
        self.assertIn(("partner_id", "=", False), duplicate_search[1])
        # Own drafts are found by marker; other uploads by vendor and number.
        self.assertIn(
            ("narration", "ilike", "[SGC-DOC %s-2]" % upload.id), duplicate_search[1]
        )
        self.assertIn(
            ("narration", "not ilike", "[SGC-DOC %s-" % upload.id), duplicate_search[1]
        )
        self.assertEqual(
            self._events(upload), ["uploaded", "booked", "booked", "failed"]
        )
        self.assertIn("USD", upload.log_ids.sorted("id")[-1].message)

    def test_review_only_bucket_is_not_booked(self):
        upload = self._upload("master_data", "Name\nSomething\n")
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "skipped")

    def test_agent_sees_target_and_booking_log(self):
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        upload.action_queue_agent()
        run = upload.agent_run_ids
        target = run.payload["target"]
        self.assertEqual(target["db_name"], "client_db")
        self.assertEqual(target["company_id"], 3)
        self.assertEqual(
            [entry["event"] for entry in run.payload["booking_log"]],
            ["booked", "booked", "uploaded"],
        )
        prompt = run._build_chat_prompt(None, [], {"total": None})
        self.assertIn('"db_name": "client_db"', prompt)
        self.assertIn("booking_log", prompt)

    def test_connection_button_lists_companies(self):
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            action = self.client.action_test_connection()
        self.assertIn("3 Target Co", action["params"]["message"])
        os.unlink(self.key_file)
        self.addCleanup(lambda: open(self.key_file, "w").close())
        with self.assertRaises(UserError):
            self.client.action_test_connection()
