# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestEnrollment(TransactionCase):

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

    def test_pending_lead_gets_enrolled_once(self):
        lead = self._make_lead()
        lead.x_nurture_state = "pending"

        Sequence = self.env["sgc.nurture.sequence"]
        Sequence._enroll_pending_leads()
        seqs = Sequence.search([("lead_id", "=", lead.id)])
        self.assertEqual(len(seqs), 1)
        self.assertEqual(seqs.status, "active")
        self.assertTrue(seqs.dry_run)
        self.assertTrue(seqs.next_touch_at)

        # A second sweep must not create a duplicate for the same lead.
        Sequence._enroll_pending_leads()
        seqs_after = Sequence.search([("lead_id", "=", lead.id)])
        self.assertEqual(len(seqs_after), 1)

    def test_lead_without_pending_state_not_enrolled(self):
        lead = self._make_lead()
        self.env["sgc.nurture.sequence"]._enroll_pending_leads()
        self.assertFalse(
            self.env["sgc.nurture.sequence"].search([("lead_id", "=", lead.id)])
        )

    def test_re_enrollment_after_stop(self):
        """A stopped sequence doesn't block a fresh enrollment if the lead
        gets flagged pending again later -- only scheduled/active/paused
        count as 'already has a live sequence'.
        """
        lead = self._make_lead()
        lead.x_nurture_state = "pending"
        Sequence = self.env["sgc.nurture.sequence"]
        Sequence._enroll_pending_leads()
        first = Sequence.search([("lead_id", "=", lead.id)])
        first.action_stop("test teardown")

        Sequence._enroll_pending_leads()
        all_seqs = Sequence.search([("lead_id", "=", lead.id)])
        self.assertEqual(len(all_seqs), 2)
        self.assertEqual(all_seqs.filtered(lambda s: s.status == "active"), all_seqs - first)
