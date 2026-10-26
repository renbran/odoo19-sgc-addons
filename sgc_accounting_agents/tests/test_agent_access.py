# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError
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
