# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSgcAgentAccess(TransactionCase):
    """Check that every agent can only do the work its role allows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create({"name": "Agent Test Company"})
        cls.roles = {
            code: cls.env["sgc.agent.role"].search([("code", "=", code)], limit=1)
            for code in (
                "agent-00-gatekeeper",
                "agent-01-intake",
                "agent-02-posting",
                "agent-03-reconciliation",
                "agent-04-tax-audit",
                "agent-05-reporting",
            )
        }
        for role in cls.roles.values():
            role.write({"company_ids": [(4, cls.company.id)]})
        cls.users = {}
        for code, role in cls.roles.items():
            cls.users[code] = cls.env["res.users"].create(
                {
                    "name": "Test %s" % code,
                    "login": "test-%s" % code,
                    "company_id": cls.company.id,
                    "company_ids": [(6, 0, [cls.company.id])],
                    "group_ids": [(6, 0, [role.group_id.id])],
                    "sgc_agent_role_id": role.id,
                }
            )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "general"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "Agent Misc",
                    "code": "AGMISC",
                    "type": "general",
                    "company_id": cls.company.id,
                }
            )
        cls.accounts = cls.env["account.account"].search(
            [("company_ids", "in", cls.company.id)], limit=2
        )
        if len(cls.accounts) < 2:
            cls.accounts = cls.env["account.account"].create(
                [
                    {
                        "name": "Agent Account One",
                        "code": "AGENT1",
                        "account_type": "asset_current",
                        "company_ids": [(6, 0, [cls.company.id])],
                    },
                    {
                        "name": "Agent Account Two",
                        "code": "AGENT2",
                        "account_type": "income",
                        "company_ids": [(6, 0, [cls.company.id])],
                    },
                ]
            )

    def _entry_values(self):
        return {
            "journal_id": self.journal.id,
            "company_id": self.company.id,
            "date": "2026-01-31",
            "line_ids": [
                (0, 0, {"account_id": self.accounts[0].id, "debit": 100.0}),
                (0, 0, {"account_id": self.accounts[1].id, "credit": 100.0}),
            ],
        }

    def test_intake_creates_contacts_only_in_its_companies(self):
        Partner = self.env["res.partner"].with_user(self.users["agent-01-intake"])
        vendor = Partner.create(
            {"name": "New Vendor LLC", "company_id": self.company.id, "supplier_rank": 1}
        )
        self.assertEqual(vendor.sudo().supplier_rank, 1)
        # Not shared with every company, not in another company, never edits.
        with self.assertRaises(AccessError):
            Partner.create({"name": "Shared Contact"})
        other = self.env["res.company"].create({"name": "Other Agent Co"})
        with self.assertRaises(AccessError):
            Partner.create({"name": "Elsewhere", "company_id": other.id})
        with self.assertRaises(AccessError):
            vendor.with_user(self.users["agent-01-intake"]).write({"name": "Renamed"})
        with self.assertRaises(AccessError):
            Partner.create(
                {"name": "Billing", "type": "invoice", "parent_id": vendor.id, "company_id": self.company.id}
            )

    def test_intake_manages_accounts_only_in_its_companies(self):
        Account = self.env["account.account"].with_user(self.users["agent-01-intake"]).with_company(self.company)
        account = Account.create(
            {"code": "611010", "name": "Office Rent", "account_type": "expense", "company_ids": [(6, 0, [self.company.id])]}
        )
        account.write({"name": "Office Rent Dubai", "reconcile": False})
        account.write({"active": False})
        self.assertFalse(account.sudo().active)
        with self.assertRaises(AccessError):
            account.unlink()
        # Only name, type, reconcile and active; never code, company, taxes.
        for vals in ({"code": "999999"}, {"company_ids": [(4, self.company.id)]}, {"tax_ids": [(5, 0, 0)]}):
            with self.assertRaises(AccessError):
                account.write(vals)
        with self.assertRaises(AccessError):
            Account.create({"code": "611013", "name": "Taxed", "account_type": "expense",
                            "company_ids": [(6, 0, [self.company.id])], "tax_ids": [(5, 0, 0)]})
        # An account with journal items keeps its type (the same type is fine).
        used = self.accounts[0].with_user(self.users["agent-01-intake"])
        self.env["account.move"].create(self._entry_values())
        used.write({"account_type": self.accounts[0].account_type, "name": "Still Current"})
        with self.assertRaises(AccessError):
            used.write({"account_type": "expense"})
        # Never an account of (or shared with) a company outside its own.
        other = self.env["res.company"].create({"name": "Other Account Co"})
        try:
            Account.create({"code": "611011", "name": "Elsewhere", "account_type": "expense",
                            "company_ids": [(6, 0, [self.company.id, other.id])]})
        except (AccessError, ValidationError):
            pass
        else:
            self.fail("intake created an account shared with another company")
        shared = self.env["account.account"].with_company(self.company).create(
            {"code": "611012", "name": "Shared", "account_type": "expense",
             "company_ids": [(6, 0, [self.company.id])]}
        )
        shared.with_company(other).code = "611012"
        shared.company_ids = [(4, other.id)]
        with self.assertRaises(AccessError):
            shared.with_user(self.users["agent-01-intake"]).write({"name": "Renamed"})

    def test_intake_creates_drafts_but_cannot_post(self):
        intake = self.users["agent-01-intake"]
        move = (
            self.env["account.move"].with_user(intake).create(self._entry_values())
        )
        self.assertEqual(move.state, "draft")
        try:
            move.with_user(intake).action_post()
            self.fail("The intake agent must not be able to post.")
        except AccessError:
            pass
        refused = self.env["sgc.agent.audit"].search(
            [("agent_user_id", "=", intake.id), ("result", "=", "refused")]
        )
        self.assertTrue(refused)

    def test_gatekeeper_cannot_write_the_ledger(self):
        gatekeeper = self.users["agent-00-gatekeeper"]
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(gatekeeper).create(
                self._entry_values()
            )

    def test_posting_agent_cannot_create_and_needs_an_approval(self):
        posting = self.users["agent-02-posting"]
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(posting).create(self._entry_values())
        move = self.env["account.move"].create(self._entry_values())
        with self.assertRaises(AccessError):
            move.with_user(posting).action_post()

    def test_posting_agent_posts_an_approved_entry(self):
        posting = self.users["agent-02-posting"]
        move = self.env["account.move"].create(self._entry_values())
        self.env["sgc.agent.posting.approval"].create(
            {
                "move_id": move.id,
                "role_id": self.roles["agent-02-posting"].id,
                "state": "approved",
                "approved_by_id": self.env.ref("base.user_admin").id,
                "approved_at": "2026-01-31 10:00:00",
            }
        )
        move.with_user(posting).action_post()
        self.assertEqual(move.state, "posted")

    def test_approval_cannot_be_granted_by_an_agent(self):
        intake = self.users["agent-01-intake"]
        move = self.env["account.move"].create(self._entry_values())
        approval = self.env["sgc.agent.posting.approval"].create(
            {"move_id": move.id, "requested_by_id": intake.id}
        )
        with self.assertRaises(Exception):
            approval.with_user(intake).action_approve()

    def test_reconciliation_cannot_create_entries(self):
        recon = self.users["agent-03-reconciliation"]
        with self.assertRaises(AccessError):
            self.env["account.move"].with_user(recon).create(self._entry_values())

    def test_audit_and_reporting_agents_are_read_only(self):
        for code in ("agent-04-tax-audit", "agent-05-reporting"):
            agent = self.users[code]
            with self.assertRaises(AccessError):
                self.env["account.move"].with_user(agent).create(
                    self._entry_values()
                )

    def test_agent_cannot_change_state_directly(self):
        intake = self.users["agent-01-intake"]
        move = (
            self.env["account.move"].with_user(intake).create(self._entry_values())
        )
        with self.assertRaises(AccessError):
            move.with_user(intake).write({"state": "posted"})
        # An XML-RPC caller controls the context: the old bypass flag is dead.
        with self.assertRaises(AccessError):
            move.with_user(intake).with_context(sgc_agent_posting=True).write(
                {"state": "posted"}
            )
        self.assertEqual(move.state, "draft")

    def test_agent_cannot_schedule_auto_post(self):
        intake = self.users["agent-01-intake"]
        Move = self.env["account.move"].with_user(intake)
        with self.assertRaises(AccessError):
            Move.create(dict(self._entry_values(), auto_post="at_date"))
        move = Move.create(self._entry_values())
        with self.assertRaises(AccessError):
            move.write({"auto_post": "at_date"})
        move.write({"auto_post": "no"})

    def test_agent_made_approval_starts_pending(self):
        intake = self.users["agent-01-intake"]
        posting = self.users["agent-02-posting"]
        move = self.env["account.move"].with_user(intake).create(self._entry_values())
        approval = (
            self.env["sgc.agent.posting.approval"]
            .with_user(intake)
            .create(
                {
                    "move_id": move.id,
                    "state": "approved",
                    "approved_by_id": self.env.ref("base.user_admin").id,
                }
            )
        )
        self.assertEqual(approval.state, "pending")
        self.assertFalse(approval.approved_by_id)
        self.assertEqual(approval.requested_by_id, intake)
        with self.assertRaises(AccessError):
            move.with_user(posting).action_post()
        with self.assertRaises(AccessError):
            self.env["sgc.agent.audit"].with_user(intake).create(
                {"agent_user_id": intake.id, "task": "x", "model_name": "x",
                 "role_id": self.roles["agent-01-intake"].id}
            )

    def test_agent_cannot_delete_or_cancel(self):
        intake = self.users["agent-01-intake"]
        move = (
            self.env["account.move"].with_user(intake).create(self._entry_values())
        )
        posted = self.env["account.move"].create(self._entry_values())
        posted.action_post()
        with self.assertRaises(AccessError):
            posted.with_user(intake).unlink()
        with self.assertRaises(AccessError):
            posted.with_user(intake).button_cancel()
        self.assertEqual(move.state, "draft")

    def test_intake_creates_draft_payments_and_cannot_confirm_them(self):
        main = self.env.company
        role = self.roles["agent-01-intake"]
        role.write({"company_ids": [(4, main.id)]})
        intake = self.env["res.users"].create(
            {
                "name": "Payment intake",
                "login": "test-payment-intake",
                "company_id": main.id,
                "company_ids": [(6, 0, [main.id])],
                "group_ids": [(6, 0, [role.group_id.id])],
                "sgc_agent_role_id": role.id,
            }
        )
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", main.id)], limit=1
        )
        values = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "amount": 50.0,
            "company_id": main.id,
            "journal_id": journal.id,
            "memo": "PAY-AGENT",
        }
        Payment = self.env["account.payment"]
        payment = Payment.with_user(intake).create(values)
        self.assertEqual(payment.state, "draft")
        for action in (
            "action_post",
            "action_validate",
            "action_reject",
            "action_cancel",
            "button_request_cancel",
            "action_draft",
        ):
            with self.assertRaises(AccessError, msg=action):
                getattr(payment.with_user(intake), action)()
        with self.assertRaises(AccessError):
            payment.with_user(intake).write({"state": "paid"})
        with self.assertRaises(AccessError):
            payment.with_user(intake).unlink()
        elsewhere = self.env["res.company"].create({"name": "Not Assigned Co"})
        with self.assertRaises(AccessError):
            Payment.with_user(intake).create(dict(values, company_id=elsewhere.id))
        with self.assertRaises(AccessError):
            Payment.with_user(self.users["agent-00-gatekeeper"]).create(values)
        payment.with_env(self.env).action_post()  # an accountant can
        self.assertNotEqual(payment.state, "draft")
