# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestEnrollment(TransactionCase):
    """Enrollment is exactly crm.lead.action_start_nurture -- a person
    clicking a button. There is no sweep of any kind; these tests call the
    action directly, the same way the "Start Nurture Sequence" button does.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage = cls.env["crm.stage"].create({"name": "Test Proposal", "sequence": 8})

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": self.stage.id,
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

    def test_pending_lead_is_eligible_and_start_creates_sequence(self):
        lead = self._make_lead()
        lead.x_nurture_state = "pending"
        self.assertTrue(lead.nurture_eligible)

        lead.action_start_nurture()

        seqs = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        self.assertEqual(len(seqs), 1)
        self.assertEqual(seqs.status, "active")
        self.assertFalse(seqs.dry_run)
        self.assertFalse(seqs.touch_ids, "starting a sequence must not draft anything")

    def test_lead_without_pending_state_not_eligible(self):
        lead = self._make_lead()
        self.assertFalse(lead.nurture_eligible)
        with self.assertRaises(UserError):
            lead.action_start_nurture()
        self.assertFalse(
            self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        )

    def test_cannot_start_twice_while_live(self):
        lead = self._make_lead()
        lead.x_nurture_state = "pending"
        lead.action_start_nurture()
        self.assertFalse(lead.nurture_eligible)
        with self.assertRaises(UserError):
            lead.action_start_nurture()
        self.assertEqual(
            len(self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])), 1)

    def test_re_enrollment_after_stop(self):
        """A stopped sequence doesn't block starting a fresh one if the lead
        gets flagged pending again later -- only scheduled/active/paused
        count as 'already has a live sequence'.
        """
        lead = self._make_lead()
        lead.x_nurture_state = "pending"
        lead.action_start_nurture()
        first = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        first.action_stop("test teardown")

        lead.x_nurture_state = "pending"
        self.assertTrue(lead.nurture_eligible)
        lead.action_start_nurture()

        all_seqs = self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        self.assertEqual(len(all_seqs), 2)
        self.assertEqual(all_seqs.filtered(lambda s: s.status == "active"), all_seqs - first)
