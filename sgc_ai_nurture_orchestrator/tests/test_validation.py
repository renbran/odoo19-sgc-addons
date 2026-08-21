# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestValidation(TransactionCase):
    """`_validate_draft` is deterministic and needs no LLM call -- these
    exercise it directly against hand-written strings, not real generations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stage = cls.env["crm.stage"].create({"name": "Test Stage", "sequence": 1})
        cls.lead = cls.env["crm.lead"].create({
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": stage.id,
            "x_bant_budget": "b", "x_bant_authority": "a", "x_bant_need": "n",
        })
        cls.seq = cls.env["sgc.nurture.sequence"].create({"lead_id": cls.lead.id})

    def test_clean_draft_passes(self):
        ok, reason = self.seq._validate_draft(
            "Hi there, just checking in on your Odoo rollout -- happy to "
            "share more whenever it's useful. No rush at all.", "whatsapp",
        )
        self.assertTrue(ok, reason)

    def test_empty_draft_blocked(self):
        ok, reason = self.seq._validate_draft("   ", "whatsapp")
        self.assertFalse(ok)

    def test_self_identifies_as_ai_blocked(self):
        ok, reason = self.seq._validate_draft(
            "Hi, as an AI assistant I wanted to follow up on your project.",
            "email",
        )
        self.assertFalse(ok)
        self.assertIn("Forbidden", reason)

    def test_guarantee_claim_blocked(self):
        ok, reason = self.seq._validate_draft(
            "We guarantee this will cut your costs in half.", "email",
        )
        self.assertFalse(ok)

    def test_fabricated_contact_claim_blocked(self):
        ok, reason = self.seq._validate_draft(
            "As I mentioned when I called you yesterday, here's the recap.",
            "whatsapp",
        )
        self.assertFalse(ok)

    def test_unsourced_currency_blocked(self):
        ok, reason = self.seq._validate_draft(
            "We can get this done for AED 15,000 flat.", "email",
        )
        self.assertFalse(ok)
        self.assertIn("currency", reason)

    def test_duplicate_recent_body_blocked(self):
        body = "Just circling back on this -- still relevant for you?"
        self.env["sgc.nurture.touch"].create({
            "sequence_id": self.seq.id,
            "touch_number": 1,
            "channel": "whatsapp",
            "body": body,
            "drafted_at": fields.Datetime.now(),
        })

        ok, reason = self.seq._validate_draft(body, "whatsapp")
        self.assertFalse(ok)
        self.assertIn("Identical", reason)
