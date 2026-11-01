# -*- coding: utf-8 -*-
import base64
import datetime
import os
import tempfile
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
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
    """The client database behind XML-RPC: only read, search_read and create
    exist, so any attempt to post (action_post) fails the test."""

    def __init__(self):
        self.calls = []
        self.existing = {}
        self.role = "agent-01-intake"
        self.create_error = None
        self.read_error = None
        self.partners = {}  # name -> contacts search_read returns for it
        self.accounts = []  # account.account search_read returns these

    def execute_kw(self, db, uid, key, model, method, args, kwargs):
        self.calls.append((db, uid, key, model, method, args, kwargs))
        if method == "create":
            if self.create_error:
                raise self.create_error
            return 100 + len([call for call in self.calls if call[4] == "create"])
        if method == "read" and model == "res.users":
            if self.read_error:
                raise self.read_error
            return [{"id": uid, "company_ids": [1, 3], "sgc_agent_role_id": [5, "R"]}]
        if method == "read" and model == "sgc.agent.role":
            return [{"id": 5, "code": self.role, "company_ids": [3]}]
        if method == "fields_get" and model == "account.account":
            return {"account_type": {"selection": [
                ["asset_current", "Current Assets"], ["income", "Income"], ["expense", "Expenses"],
            ]}}
        if method == "write" and model == "account.account":
            return True
        if method != "search_read":
            raise AssertionError("unexpected call %s.%s" % (model, method))
        if model == "account.account":
            return self.accounts
        domain = args[0]
        if model == "res.partner":
            for name, records in self.partners.items():
                if ("name", "=ilike", name) in domain:
                    return records
            if ("name", "=ilike", "Known Customer") in domain:
                return [{"id": 7}]
            # A contact created earlier (ids as create returns them) is found.
            creates = [call for call in self.calls if call[4] == "create"]
            return [
                {"id": 100 + n}
                for n, call in enumerate(creates, 1)
                if call[3] == "res.partner" and ("name", "=ilike", call[5][0]["name"]) in domain
            ][:1]
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

    def created(self, model=None):
        """Created records of ``model``; by default the drafts (not contacts)."""
        return [
            call for call in self.calls
            if call[4] == "create" and (call[3] == model if model else call[3] != "res.partner")
        ]


OWNER = "owner@client.test"

CHART = (
    "Action,Account Code,Account Name,Account Type,Allow Reconciliation\n"
    "Create,5096,Transportation,Expense (Contra),No\n"
    "Create,5097,Existing Fees,Expenses,No\n"
    "Update,1100,,Current Assets,Yes\n"
    "Archive,5000,,,\n"
)


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
        # The client's portal user, verified in client_db by the link script.
        cls.owner = cls.env["res.users"].create(
            {
                "name": "Booking Owner",
                "login": OWNER,
                "partner_id": partner.id,
                "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
            }
        )
        cls.client.owner_user_id = cls.owner
        cls.client.link_owner_login = OWNER
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
        self._write_key()
        self.addCleanup(os.unlink, self.key_file)
        patcher = patch.object(accounting_client, "SECRETS_DIR", secrets)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.db = FakeDatabase()

    def _write_key(self, days=60, **overrides):
        """A key file as scripts/link_accounting_client.sh writes it."""
        values = {
            "SGC_AGENT_ROLE": "agent-01-intake",
            "SGC_AGENT_LOGIN": "svc-agent-01-intake@sgctech.ai",
            "SGC_AGENT_USER_ID": "12",
            "SGC_AGENT_API_KEY": "client-key",
            "SGC_AGENT_ODOO_URL": "https://client.test",
            "SGC_AGENT_DB": "client_db",
            "SGC_AGENT_KEY_EXPIRES": (
                datetime.datetime.now() + datetime.timedelta(days=days)
            ).isoformat(),
        }
        values.update(overrides)
        with open(self.key_file, "w", encoding="utf-8") as handle:
            handle.write("".join("%s=%s\n" % item for item in values.items()))

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
        for db, uid, key, model, _method, _args, kwargs in self.db.calls:
            self.assertEqual((db, uid, key), ("client_db", 12, "client-key"))
            if model not in ("res.users", "sgc.agent.role", "res.company"):
                self.assertEqual(kwargs["context"], {"allowed_company_ids": [3]})
        # The intake identity is checked before anything is created.
        self.assertEqual(self.db.calls[0][3:5], ("res.users", "read"))
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
        # A new customer is created once, in the target company, as a customer.
        (partner,) = (call[5][0] for call in self.db.created("res.partner"))
        self.assertEqual(
            (partner["name"], partner["company_id"], partner["customer_rank"]),
            ("New Customer", 3, 1),
        )
        self.assertEqual(second["partner_id"], 102)
        self.assertIn("New Customer was new", second["narration"])
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
        row_key = created[1][5][0]["memo"]
        self.assertRegex(row_key, r"^SGC-[0-9a-f]{12}-1$")
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
        # The same file sent again keys that row the same way, so the
        # duplicate check looks for the first draft, not a fresh key.
        self._upload("payments", PAYMENTS)
        self._book()
        searched = [
            call[5][0] for call in self.db.calls
            if call[3] == "account.payment" and call[4] == "search_read"
        ]
        self.assertEqual(searched[-1][0], ("memo", "=", row_key))
        # Two identical rows in one file stay two payments.
        seen, row = {}, {"Amount": "20"}
        self.assertNotEqual(upload._row_key(row, seen), upload._row_key(row, seen))

    def test_unlinked_client_waits_then_books(self):
        self.client.base_url = False
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "waiting")
        self.assertEqual(self._events(upload), ["uploaded", "waiting"])
        self.assertFalse(upload.target_base_url)
        self.client.write({"base_url": "https://client.test", "link_owner_login": OWNER})
        self._book()
        self.assertEqual(upload.target_base_url, "https://client.test")
        self.assertEqual(upload.booking_state, "done")
        self.assertEqual(len(self.db.created()), 2)

    def test_snapshot_does_not_follow_a_relinked_client(self):
        upload = self._upload("customer_invoices", INVOICES)
        self.client.write({"db_name": "other_db", "link_owner_login": OWNER})
        self._write_key(SGC_AGENT_DB="other_db")
        upload._snapshot_target()
        self.assertEqual(upload.target_db, "client_db")
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "failed")
        self.assertIn("other_db", upload.log_ids.sorted("id")[-1].message)

    def test_connection_needs_https_and_its_own_key_file(self):
        self.client.base_url = "http://client.test"
        self.assertIn("https", self.client._booking_connection()[1])
        self.client.write({"base_url": "https://client.test", "link_owner_login": OWNER})
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
        (vendor,) = (call[5][0] for call in self.db.created("res.partner"))
        self.assertEqual((vendor["name"], vendor["supplier_rank"]), ("Other Vendor", 1))
        self.assertEqual(created[1]["partner_id"], 102)
        duplicate_search = [
            call[5][0] for call in self.db.calls
            if call[3] == "account.move" and call[4] == "search_read"
        ]
        self.assertIn(("partner_id", "=", 7), duplicate_search[0])
        self.assertIn(("partner_id", "=", 102), duplicate_search[1])
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
        action = self.client.action_test_connection()
        self.assertEqual(action["params"]["type"], "danger")
        self.assertIn("cannot be read", self.client.last_error)

    def _agency_manager(self):
        return self.env["res.users"].create(
            {
                "name": "Agency Manager",
                "login": "agency-manager-test",
                "group_ids": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("sgc_accounting_clients.group_sgc_accounting_manager").id),
                ],
            }
        )

    def test_non_intake_api_user_never_books(self):
        # A posting agent's key could post: refuse it before creating anything.
        manager = self._agency_manager()
        self.db.role = "agent-02-posting"
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertFalse(self.db.created())
        self.assertEqual(upload.booking_state, "waiting")
        self.assertIn("not the agent-01-intake agent", upload.log_ids.sorted("id")[-1].message)
        # OdooBot is the account manager here: the to-do goes to an agency manager.
        self.assertEqual(self.client.activity_ids.user_id, manager)
        # Link repaired: the waiting upload is booked by the next run.
        self.db.role = "agent-01-intake"
        self._book()
        self.assertEqual(upload.booking_state, "done")
        self.assertTrue(self.db.created())

    def test_key_file_must_match_the_link(self):
        self._write_key(SGC_AGENT_DB="another_db")
        conn, error = self.client._booking_connection()
        self.assertIsNone(conn)
        self.assertIn("database", error)
        self._write_key(days=-1)
        self.assertIn("expired", self.client._booking_connection()[1])
        self._write_key(SGC_AGENT_ROLE="agent-02-posting")
        self.assertIn("only agent-01-intake", self.client._booking_connection()[1])

    def test_network_problems_are_retried_then_fail(self):
        self._agency_manager()
        self.db.create_error = ConnectionRefusedError("connection refused")
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertEqual(upload.booking_state, "pending")
        self.assertEqual(upload.booking_attempts, 1)
        for _attempt in range(4):
            self._book()
        self.assertEqual(upload.booking_state, "failed")
        self.assertEqual(upload.activity_ids.summary, "Draft booking failed")
        self.db.create_error = None
        tried = len(self.db.created())
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            upload.action_book_drafts()
        self.assertEqual(upload.booking_state, "done")
        self.assertEqual(upload.booking_attempts, 0)
        self.assertEqual(len(self.db.created()) - tried, 2)
        self.assertFalse(upload.activity_ids)
        # A booked upload is not booked again by the button.
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            upload.action_book_drafts()
        self.assertEqual(len(self.db.created()) - tried, 2)

    def test_unlinked_client_cannot_starve_the_others(self):
        partner = self.env["res.partner"].create({"name": "Abandoned Trial"})
        trial = self.env["sgc.accounting.client"].create(
            {"name": "Abandoned Trial", "client_code": "abandoned-trial", "partner_id": partner.id}
        )
        Upload = self.env["sgc.accounting.upload"]
        stuck = Upload.browse()
        for index in range(3):
            stuck |= Upload.create({
                "client_id": trial.id, "doc_type": "customer_invoices",
                "filename": "old%s.csv" % index,
                "file": base64.b64encode(INVOICES.encode("utf-8")),
            })
        upload = self._upload("customer_invoices", INVOICES)
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            Upload._cron_book_pending(limit=1)
        # Parking the unlinked client's uploads costs nothing against the limit.
        self.assertEqual(upload.booking_state, "done")
        self.assertEqual(stuck.mapped("booking_state"), ["waiting"] * 3)

    def test_unreachable_database_waits_without_spending_retries(self):
        self.db.read_error = ConnectionRefusedError("connection refused")
        first = self._upload("customer_invoices", INVOICES)
        second = self._upload("vendor_bills", VENDOR_BILLS)
        self._book()
        self.assertEqual(first.booking_state, "waiting")
        self.assertEqual(first.booking_attempts, 0)
        # One probe per client per run: the second upload was not tried.
        self.assertEqual(second.booking_state, "pending")
        self.assertEqual(
            len([c for c in self.db.calls if c[3] == "res.users"]), 1
        )
        self.db.read_error = None
        self._book()
        self.assertEqual(first.booking_state, "done")

    def test_company_not_allowed_fails_only_that_upload(self):
        other = self.env["sgc.accounting.company"].create(
            {"client_id": self.client.id, "odoo_company_id": 1, "name": "Parent"}
        )
        dropped = self._upload("customer_invoices", INVOICES)
        dropped.accounting_company_id = other
        dropped.target_company_ref = 1
        fine = self._upload("vendor_bills", VENDOR_BILLS)
        self._book()
        self.assertEqual(dropped.booking_state, "failed")
        self.assertIn("may not book into company id 1", dropped.log_ids.sorted("id")[-1].message)
        self.assertNotEqual(fine.booking_state, "waiting")
        self.assertTrue(self.db.created())

    def test_same_reference_for_another_document_is_flagged(self):
        # Numbers restarted, or a customer PO in ref: not this invoice.
        self.db.existing["account.move"] = [{
            "id": 56, "name": "INV/2025/0001", "state": "posted",
            "partner_id": [99, "Someone Else"], "invoice_date": "2025-01-05",
        }]
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertFalse(self.db.created())
        self.assertEqual(upload.booking_state, "failed")
        self.assertEqual(self._events(upload), ["uploaded", "failed", "failed"])
        messages = " ".join(upload.log_ids.mapped("message"))
        self.assertIn("is for another party", messages)
        self.assertIn("is dated 2025-01-05", messages)

    def test_own_draft_edited_by_an_accountant_stays_a_duplicate(self):
        upload = self._upload("customer_invoices", INVOICES)
        self.db.existing["account.move"] = [{
            "id": 57, "name": "/", "state": "draft", "partner_id": [7, "Known"],
            "invoice_date": "2026-01-01", "narration": "[SGC-DOC %s-1]" % upload.id,
        }]
        self._book()
        self.assertFalse(self.db.created())
        # INV-1 is our own (re-dated) draft; INV-2 only shares the reference.
        self.assertEqual(self._events(upload), ["uploaded", "duplicate", "failed"])

    def test_same_day_payment_with_another_amount_is_flagged(self):
        self.db.existing["account.payment"] = [{
            "id": 70, "name": "P1", "state": "draft", "partner_id": [7, "Known"],
            "date": "2026-10-23", "amount": 500.0,
        }]
        upload = self._upload("payments", PAYMENTS)
        self._book()
        self.assertFalse(self.db.created())
        self.assertIn("is for 500.0", " ".join(upload.log_ids.mapped("message")))

    def test_unreadable_key_file_is_recorded(self):
        with open(self.key_file, "wb") as handle:
            handle.write(bytes([0xFF, 0xFE]) + b" not utf-8")
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            self.env["sgc.accounting.client"]._cron_check_connections()
        self.assertIn("cannot be read", self.client.last_error)

    def test_health_check_warns_before_the_key_expires(self):
        manager = self._agency_manager()
        self._write_key(days=5)
        for _run in range(2):
            with patch("xmlrpc.client.ServerProxy", return_value=self.db):
                self.env["sgc.accounting.client"]._cron_check_connections()
        self.assertTrue(self.client.last_health_check)
        self.assertFalse(self.client.last_error)
        self.assertEqual(len(self.client.activity_ids), 1)
        self.assertEqual(self.client.activity_ids.user_id, manager)
        self.assertIn("expires", str(self.client.activity_ids.note))
        # A new problem replaces the reason on the same to-do.
        self.db.role = "agent-02-posting"
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            self.client._check_connection()
        self.assertEqual(len(self.client.activity_ids), 1)
        self.assertIn("not the agent-01-intake agent", str(self.client.activity_ids.note))
        self.db.role = "agent-01-intake"
        # Rotated: the next check closes the alarm.
        self._write_key(days=90)
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            self.client._check_connection()
        self.assertFalse(self.client.activity_ids)

    def test_agent_review_task_is_not_duplicated(self):
        manager = self._agency_manager()
        upload = self._upload("master_data", "Name\nX\n")
        upload._assign_agent_review(True)
        upload._assign_agent_review(True)
        self.assertEqual(len(upload.activity_ids), 1)
        self.assertEqual(upload.activity_ids.user_id, manager)

    def test_link_changed_by_hand_is_not_verified(self):
        # Editing the database by hand clears the verified owner, even when
        # it is set back: nothing is sent until the link script verifies it.
        self.client.db_name = "client_db_typo"
        self.client.db_name = "client_db"
        self.assertFalse(self.client.link_owner_login)
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "waiting")
        self.assertIn("not verified", upload.log_ids.sorted("id")[-1].message)

    def test_owner_who_left_the_client_stops_booking(self):
        self.owner.login = "someone-else@client.test"
        upload = self._upload("customer_invoices", INVOICES)
        self._book()
        self.assertFalse(self.db.calls)
        self.assertEqual(upload.booking_state, "waiting")

    def test_dates_follow_the_files_order(self):
        month_first = VENDOR_BILLS.replace("2026-10-20", "4/2/2026").replace(
            "2026-11-19", "4/21/2026"
        )
        self._upload("vendor_bills", month_first)
        self._book()
        created = [call[5][0] for call in self.db.created()]
        self.assertEqual(
            [(v["invoice_date"], v["invoice_date_due"]) for v in created],
            [("2026-04-02", "2026-04-21")] * 2,
        )

    def test_day_first_dates(self):
        self._upload("vendor_bills", VENDOR_BILLS.replace("2026-10-20", "21.04.2026"))
        self._book()
        created = [call[5][0] for call in self.db.created()]
        self.assertEqual({v["invoice_date"] for v in created}, {"2026-04-21"})

    def test_dates_that_fit_both_orders_are_refused(self):
        for bill_date, due_date, words in (
            ("4/2/2026", "4/3/2026", "can be read as day/month or month/day"),
            ("4/21/2026", "21/4/2026", "mixes day-first"),
        ):
            upload = self._upload(
                "vendor_bills",
                VENDOR_BILLS.replace("2026-10-20", bill_date).replace("2026-11-19", due_date),
            )
            self._book()
            self.assertEqual(upload.booking_state, "failed")
            self.assertIn(words, upload.log_ids.sorted("id")[-1].message)
        self.assertFalse(self.db.created())

    def test_staff_of_the_client_partner_is_not_an_owner(self):
        staff = self.env["res.users"].create(
            {"name": "Staff", "login": "staff@firm.test", "partner_id": self.client.partner_id.id}
        )
        self.assertFalse(staff.share)
        self.assertEqual(self.client._owner_logins(), {OWNER})

    def test_only_the_registered_login_is_the_owner(self):
        colleague = self.env["res.partner"].create(
            {"name": "Colleague", "parent_id": self.client.partner_id.id}
        )
        self.env["res.users"].create(
            {
                "name": "Colleague",
                "login": "colleague@client.test",
                "partner_id": colleague.id,
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        self.assertEqual(self.client._owner_logins(), {OWNER})
        staff = self.env["res.users"].create({"name": "Staff", "login": "staff2@firm.test"})
        with self.assertRaises(ValidationError):
            self.client.owner_user_id = staff
        stranger = self.env["res.users"].create(
            {
                "name": "Stranger",
                "login": "stranger@else.test",
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        with self.assertRaises(ValidationError):
            self.client.owner_user_id = stranger

    def test_chart_of_accounts_waits_for_the_owner_then_applies(self):
        self.db.accounts = [
            {"id": 41, "code": "5097", "name": "Existing Fees", "active": True, "company_ids": [3]},
            {"id": 42, "code": "1100", "name": "Debtors", "active": True, "company_ids": [3]},
            {"id": 43, "code": "5000", "name": "Old Account", "active": True, "company_ids": [3]},
        ]
        upload = self._upload("chart_of_accounts", CHART)
        self.assertEqual(upload.booking_state, "approval")
        self._book()
        self.assertEqual(upload.booking_state, "approval")  # never without the owner
        self.assertFalse([call for call in self.db.calls if call[3] == "account.account"])
        colleague = self.env["res.users"].create(
            {
                "name": "Colleague",
                "login": "colleague@client.test",
                "partner_id": self.client.partner_id.id,
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        self.assertFalse(upload._owner_approve(colleague, upload.sha256))
        # Only the file the owner was shown.
        self.assertFalse(upload._owner_approve(self.owner, "0" * 64))
        self.assertTrue(upload._owner_approve(self.owner, upload.sha256))
        self._book()
        self.assertEqual(upload.booking_state, "done")
        created = self.db.created("account.account")
        self.assertEqual(len(created), 1)
        self.assertEqual(
            created[0][5][0],
            {"code": "5096", "name": "Transportation", "account_type": "expense",
             "reconcile": False, "company_ids": [(6, 0, [3])]},
        )
        self.assertEqual(created[0][6]["context"], {"allowed_company_ids": [3]})
        writes = [(call[5][0], call[5][1]) for call in self.db.calls if call[4] == "write"]
        self.assertEqual(
            writes, [([42], {"account_type": "asset_current", "reconcile": True}), ([43], {"active": False})]
        )
        self.assertEqual(
            self._events(upload), ["uploaded", "approved", "applied", "duplicate", "applied", "applied"]
        )
        self.assertFalse(upload._owner_approve(self.owner, upload.sha256))  # only once

    def _account_calls(self):
        return [call for call in self.db.calls if call[3] == "account.account"]

    def test_chart_of_accounts_needs_the_owners_approval_of_this_file(self):
        upload = self._upload("chart_of_accounts", CHART)
        # An old upload pushed by the staff button goes back to the owner.
        upload.booking_state = False
        with patch("xmlrpc.client.ServerProxy", return_value=self.db):
            upload.action_book_drafts()
        self.assertEqual(upload.booking_state, "approval")
        self.assertEqual(self._events(upload)[-1], "approval")
        # Staff cannot approve for the owner, nor move the document.
        staff = self.env["res.users"].create(
            {
                "name": "Agency User",
                "login": "agency-user@firm.test",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("sgc_accounting_clients.group_sgc_accounting_manager").id),
                ],
            }
        )
        with self.assertRaises(AccessError):
            upload.with_user(staff).write({"approved_by_id": self.owner.id, "approved_sha256": upload.sha256})
        other = self.env["sgc.accounting.client"].create(
            {"name": "Other", "client_code": "other-client", "partner_id": self.env["res.partner"].create({"name": "Other"}).id}
        )
        with self.assertRaises(UserError):
            upload.write({"client_id": other.id})
        # Approved, then the file changes: the new file needs a new approval.
        self.assertTrue(upload._owner_approve(self.owner, upload.sha256))
        upload.file = base64.b64encode(CHART.replace("Transportation", "Travel").encode())
        self._book()
        self.assertEqual(upload.booking_state, "approval")
        self.assertFalse(self._account_calls())

    def test_chart_of_accounts_never_touches_a_shared_account(self):
        self.db.accounts = [{"id": 42, "code": "1100", "name": "Debtors", "active": True, "company_ids": [3, 9]}]
        upload = self._upload("chart_of_accounts", CHART)
        upload._owner_approve(self.owner, upload.sha256)
        self._book()
        self.assertEqual(upload.booking_state, "approval")
        self.assertIn("1100 is shared", upload.log_ids.sorted("id")[-1].message)
        self.assertFalse([call for call in self._account_calls() if call[4] in ("create", "write")])

    def test_an_unchanged_link_keeps_its_verified_owner(self):
        self.client.write({"base_url": self.client.base_url.upper() + "/", "db_name": self.client.db_name, "api_user_id": 12})
        self.assertEqual(self.client.link_owner_login, OWNER)

    def test_chart_of_accounts_with_a_bad_row_changes_nothing(self):
        upload = self._upload(
            "chart_of_accounts",
            CHART.replace("Current Assets", "Planets").replace("Archive,5000", "Delete,5000"),
        )
        upload._owner_approve(self.owner, upload.sha256)
        self._book()
        # Back to the owner, with the reason and the valid types.
        self.assertEqual(upload.booking_state, "approval")
        self.assertFalse(upload.approved_by_id)
        message = upload.log_ids.sorted("id")[-1].message
        self.assertIn("Nothing was changed", message)
        self.assertIn("row 4", message)
        self.assertIn("row 5", message)
        self.assertIn("Account types: Current Assets, Income, Expenses", message)
        self.assertFalse([call for call in self.db.calls if call[4] in ("create", "write")])

    def test_only_the_link_script_sets_the_owner(self):
        manager = self.env["res.users"].create(
            {
                "name": "Accounting User",
                "login": "acc-user@firm.test",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("sgc_accounting_clients.group_sgc_accounting_user").id),
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.client.with_user(manager).write({"link_owner_login": OWNER})
        with self.assertRaises(AccessError):
            self.env["sgc.accounting.client"].with_user(manager).create(
                {"name": "X", "client_code": "x-client", "partner_id": self.client.partner_id.id,
                 "link_owner_login": OWNER}
            )

    def test_a_typo_does_not_set_the_date_order(self):
        upload = self._upload(
            "vendor_bills",
            VENDOR_BILLS.replace("2026-10-20", "3/4/2026").replace("2026-11-19", "41/3/2026"),
        )
        self._book()
        self.assertFalse(self.db.created())
        self.assertIn("can be read as day/month", upload.log_ids.sorted("id")[-1].message)

    def test_new_vendor_is_created_once_per_file(self):
        bills = VENDOR_BILLS.replace("Known Customer", "Other Vendor").replace(",USD,", ",AED,")
        self._upload("vendor_bills", bills)
        self._book()
        (vendor,) = self.db.created("res.partner")
        vendor_id = 100 + [c for c in self.db.calls if c[4] == "create"].index(vendor) + 1
        self.assertEqual({call[5][0]["partner_id"] for call in self.db.created()}, {vendor_id})
        self.assertEqual(len(self.db.created()), 2)

    def test_partner_names_match_exactly(self):
        self._upload("vendor_bills", VENDOR_BILLS.replace("Other Vendor", "50%_Off Co"))
        self._book()
        searches = [
            call[5][0] for call in self.db.calls
            if call[3] == "res.partner" and call[4] == "search_read"
        ]
        self.assertIn(("name", "=ilike", r"50\%\_Off Co"), searches[-1])

    def test_contact_choice_never_guesses(self):
        bill = VENDOR_BILLS.replace("Other Vendor", "Known Customer").replace(",USD,", ",AED,")
        # The company's own contact wins over a shared one with that name.
        self.db.partners["Known Customer"] = [
            {"id": 21, "company_id": False, "active": True},
            {"id": 22, "company_id": [3, "Target Co"], "active": True},
        ]
        self._upload("vendor_bills", bill)
        self._book()
        self.assertEqual({c[5][0]["partner_id"] for c in self.db.created()}, {22})
        search = next(c[5][0] for c in self.db.calls if c[3] == "res.partner")
        self.assertIn(("parent_id", "=", False), search)  # never a contact person
        self.assertIn(("active", "in", [True, False]), search)
        # Two at the same level, or an archived one: that document fails.
        for records, words in (
            ([{"id": 23, "company_id": False}, {"id": 24, "company_id": False}], "2 contacts are named"),
            ([{"id": 25, "company_id": [3, "Target Co"], "active": False}], "archived"),
        ):
            self.db = FakeDatabase()
            self.db.partners["Known Customer"] = records
            upload = self._upload("vendor_bills", bill.replace("100", "101"))
            self._book()
            self.assertFalse(self.db.created())
            self.assertIn(words, upload.log_ids.sorted("id")[-1].message)
