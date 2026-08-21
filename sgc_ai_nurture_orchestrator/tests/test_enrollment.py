# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestEnrollment(TransactionCase):
    """Enrollment is exactly crm.lead.action_start_nurture -- a person
    clicking a button. There is no sweep of any kind; these tests call the
    action directly, the same way the "Start Nurture Sequence" button does.

    Eligibility is deliberately broad: any active lead with no live
    sequence, any stage -- NOT gated behind sgc_proposal_nurture's 3-day
    Proposal-stall flag. A rep must be able to start nurture on a lead in
    New, not only wait for a flag scoped to Proposal-stage leads.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_new = cls.env["crm.stage"].create({"name": "Test New", "sequence": 1})
        cls.stage_proposal = cls.env["crm.stage"].create(
            {"name": "Test Proposal", "sequence": 8})

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": self.stage_new.id,
            # sgc_crm_ai_compat (unrelated to this module, if installed)
            # blocks any stage_id write until 3 of 4 BANT fields are filled --
            # pre-filled here so enrollment tests aren't incidentally blocked
            # by a completely separate gate. See sgc_sales_playbook's own
            # tests for the same landmine.
            "x_bant_budget": "Budget filled",
            "x_bant_authority": "Authority filled",
            "x_bant_need": "Need filled",
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def test_new_stage_lead_with_no_flag_is_eligible(self):
        """The exact gap reported: a lead in New, with no
        sgc_proposal_nurture flag at all, must still be startable.
        """
        lead = self._make_lead()
        self.assertFalse(lead.x_nurture_state)
        self.assertTrue(lead.nurture_eligible)

        lead.action_start_nurture()

        seqs = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        self.assertEqual(len(seqs), 1)
        self.assertEqual(seqs.status, "active")
        self.assertFalse(seqs.dry_run)
        self.assertFalse(seqs.touch_ids, "starting a sequence must not draft anything")
        self.assertEqual(seqs.sequence_type, "manual")

    def test_proposal_stall_flag_recorded_as_reason_not_a_gate(self):
        lead = self._make_lead(stage_id=self.stage_proposal.id)
        lead.x_nurture_state = "pending"

        lead.action_start_nurture()

        seq = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        self.assertEqual(seq.sequence_type, "proposal_stall")

    def test_lost_lead_not_eligible(self):
        lead = self._make_lead()
        lead.write({"active": False})
        self.assertFalse(lead.nurture_eligible)
        with self.assertRaises(UserError):
            lead.action_start_nurture()

    def test_cannot_start_twice_while_live(self):
        lead = self._make_lead()
        lead.action_start_nurture()
        self.assertFalse(lead.nurture_eligible)
        with self.assertRaises(UserError):
            lead.action_start_nurture()
        self.assertEqual(
            len(self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])), 1)

    def test_re_enrollment_after_stop(self):
        """A stopped sequence doesn't block starting a fresh one later --
        only scheduled/active/paused count as 'already has a live sequence'.
        """
        lead = self._make_lead()
        lead.action_start_nurture()
        first = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        first.action_stop("test teardown")

        self.assertTrue(lead.nurture_eligible)
        lead.action_start_nurture()

        all_seqs = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        self.assertEqual(len(all_seqs), 2)
        self.assertEqual(all_seqs.filtered(lambda s: s.status == "active"), all_seqs - first)
