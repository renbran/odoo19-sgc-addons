# -*- coding: utf-8 -*-
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_sales_playbook")
class TestSalesPlaybookGate(TransactionCase):
    """Covers B2 (self-granted override), B3 (Meeting Booked -> Won skip),
    and S2 (gate_mode) regressions, plus the base gate-pass/gate-block
    behaviour they build on. Stage records are created locally with
    controlled sequences rather than relying on any specific database's
    live crm.stage ids/sequences."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Stage = cls.env["crm.stage"]
        cls.stage_new = Stage.create({"name": "Test New", "sequence": 0})
        cls.stage_meeting = Stage.create({"name": "Test Meeting Booked", "sequence": 7})
        cls.stage_proposal = Stage.create({"name": "Test Proposal", "sequence": 8})
        cls.stage_won = Stage.create({"name": "Test Won", "sequence": 9, "is_won": True})
        cls.stage_dead_end = Stage.create({"name": "Test Dead End", "sequence": 10})

        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.gate_stage_id", str(cls.stage_proposal.id))
        ICP.set_param("sgc_sales_playbook.gate_excluded_stage_ids", str(cls.stage_dead_end.id))
        ICP.set_param("sgc_sales_playbook.gate_mode", "block")

        cls.manager = cls.env["res.users"].create({
            "name": "Test Sales Manager",
            "login": "test_sales_manager_gate",
            "email": "test_sales_manager_gate@example.com",
            "group_ids": [(6, 0, [cls.env.ref("sales_team.group_sale_manager").id])],
        })
        cls.salesman = cls.env["res.users"].create({
            "name": "Test Salesman",
            "login": "test_salesman_gate",
            "email": "test_salesman_gate@example.com",
            "group_ids": [(6, 0, [cls.env.ref("sales_team.group_sale_salesman").id])],
        })

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": self.stage_new.id,
            # sgc_crm_ai_compat (pre-existing, unrelated to this module)
            # requires 3 of 4 BANT fields filled before ANY stage_id write
            # succeeds — discovered while first running these tests against
            # the full production module set. Not something this module's
            # tests are meant to exercise; pre-filled here so gate tests
            # aren't incidentally blocked by a completely separate gate.
            "x_bant_budget": "Budget filled",
            "x_bant_authority": "Authority filled",
            "x_bant_need": "Need filled",
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _fill_gate(self, lead):
        lead.write({
            "x_gate_problem": "Problem",
            "x_gate_cost_of_inaction": "Cost",
            "x_gate_approver": "Approver",
            "x_gate_timeline": "Timeline",
        })

    def _set_gate_mode(self, mode):
        self.env["ir.config_parameter"].sudo().set_param("sgc_sales_playbook.gate_mode", mode)

    def test_gate_blocks_at_0_of_4_in_block_mode(self):
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        with self.assertRaises(UserError):
            lead.write({"stage_id": self.stage_proposal.id})

    def test_gate_passes_at_4_of_4(self):
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        self._fill_gate(lead)
        lead.write({"stage_id": self.stage_proposal.id})
        self.assertEqual(lead.stage_id, self.stage_proposal)

    def test_gate_warns_but_allows_in_warn_mode(self):
        self._set_gate_mode("warn")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        lead.write({"stage_id": self.stage_proposal.id})
        self.assertEqual(lead.stage_id, self.stage_proposal)
        self.assertTrue(
            any("gate_mode=warn" in (m.body or "") for m in lead.message_ids)
        )

    def test_gate_off_disables_entirely(self):
        self._set_gate_mode("off")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        lead.write({"stage_id": self.stage_proposal.id})
        self.assertEqual(lead.stage_id, self.stage_proposal)

    def test_manager_override_succeeds_via_wizard(self):
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        wizard = self.env["sgc.gate.override.wizard"].with_user(self.manager).create({
            "lead_id": lead.id,
            "reason": "Verbal commitment from CFO, formal answers pending.",
        })
        wizard.with_user(self.manager).action_confirm()
        self.assertEqual(lead.stage_id, self.stage_proposal)
        self.assertEqual(
            lead.x_gate_override_reason,
            "Verbal commitment from CFO, formal answers pending.",
        )

    def test_non_manager_cannot_create_override_wizard(self):
        """ACL layer: salesmen have no access rows at all on this wizard
        model — confirmed the actual failure mode is an AccessError on
        create(), before action_confirm()'s own check is ever reached."""
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        with self.assertRaises(AccessError):
            self.env["sgc.gate.override.wizard"].with_user(self.salesman).create({
                "lead_id": lead.id,
                "reason": "trying to bypass",
            })

    def test_non_manager_override_wizard_confirm_refused_defense_in_depth(self):
        """Business-logic layer: action_confirm() itself refuses even if a
        non-manager somehow already holds a wizard record (ACLs loosened
        later, record created on their behalf via sudo) — defense in
        depth, not the primary control (mirrors write()'s own reasoning
        for B2)."""
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        wizard = self.env["sgc.gate.override.wizard"].sudo().create({
            "lead_id": lead.id,
            "reason": "trying to bypass",
        })
        with self.assertRaises(UserError):
            wizard.with_user(self.salesman).action_confirm()

    def test_non_manager_override_refused_via_direct_write(self):
        """B2 regression: groups= on the field is view-level only, not an
        ORM write() guard, so write() itself must re-check has_group()."""
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        with self.assertRaises(UserError):
            lead.with_user(self.salesman).write({
                "stage_id": self.stage_proposal.id,
                "x_gate_override_reason": "self-granted bypass attempt",
            })
        self.assertNotEqual(lead.stage_id, self.stage_proposal)

    def test_meeting_booked_to_won_is_gated(self):
        """B3 regression: sequence-threshold gate must catch a direct jump
        past Proposal, not just entry into Proposal itself."""
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        with self.assertRaises(UserError):
            lead.write({"stage_id": self.stage_won.id})

    def test_dead_end_stage_never_gated(self):
        """B3 edge case: dead-end stages sit at a higher sequence than Won
        but must never require the gate."""
        self._set_gate_mode("block")
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        lead.write({"stage_id": self.stage_dead_end.id})
        self.assertEqual(lead.stage_id, self.stage_dead_end)

    def test_gate_fails_open_on_unresolvable_gate_stage(self):
        self._set_gate_mode("block")
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_sales_playbook.gate_stage_id", "999999"
        )
        lead = self._make_lead(stage_id=self.stage_meeting.id)
        lead.write({"stage_id": self.stage_proposal.id})
        self.assertEqual(lead.stage_id, self.stage_proposal)
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_sales_playbook.gate_stage_id", str(self.stage_proposal.id)
        )
