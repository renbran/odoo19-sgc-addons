# -*- coding: utf-8 -*-
from unittest.mock import Mock, patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestCadence(TransactionCase):
    """Drafting goes through llm.provider._make_request, which shells out
    via `requests.post` -- mocked here exactly the way sgc_lead_scoring's
    own tests mock it, so these never hit a real network/API.
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
        cls.provider = cls.env["llm.provider"].create({
            "name": "Test Provider",
            "provider_type": "groq",
            "api_key": "test-key",
            "model_name": "test-model",
            "is_default": True,
        })

    def _make_seq(self):
        return self.env["sgc.nurture.sequence"].create({
            "lead_id": self.lead.id, "status": "active",
            "next_touch_at": fields.Datetime.now(),
        })

    def _mock_response(self, text):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": text}}]}
        return mock_response

    @patch("requests.post")
    def test_first_touch_drafts_and_advances(self, mock_post):
        mock_post.return_value = self._mock_response(
            "Hi there, just wanted to check in about your Odoo project. "
            "Happy to chat whenever suits you.")
        seq = self._make_seq()

        seq._process_one()

        self.assertEqual(seq.current_touch, 1)
        self.assertTrue(seq.next_touch_at)
        touches = seq.touch_ids
        self.assertEqual(len(touches), 1)
        self.assertEqual(touches.channel, "whatsapp")
        self.assertEqual(touches.delivery_status, "skipped_dry_run")
        self.assertTrue(touches.body)

    @patch("requests.post")
    def test_blocked_draft_still_advances_counter(self, mock_post):
        mock_post.return_value = self._mock_response(
            "As an AI assistant, I guarantee this will work for you.")
        seq = self._make_seq()

        seq._process_one()

        self.assertEqual(seq.current_touch, 1)
        self.assertEqual(seq.touch_ids.delivery_status, "validation_blocked")
        self.assertNotEqual(seq.status, "exhausted")

    @patch("requests.post")
    def test_five_touches_then_exhausted(self, mock_post):
        mock_post.return_value = self._mock_response(
            "Just checking in -- still relevant for you? No pressure either way.")
        seq = self._make_seq()

        for _ in range(5):
            seq.next_touch_at = fields.Datetime.now()
            seq._process_one()

        self.assertEqual(seq.current_touch, 5)
        self.assertEqual(len(seq.touch_ids), 5)
        self.assertEqual(seq.status, "active")  # 6th call is what flips it

        seq.next_touch_at = fields.Datetime.now()
        seq._process_one()
        self.assertEqual(seq.status, "exhausted")
        self.assertEqual(seq.stop_event, "exhausted")
        # No 6th touch row -- exhaustion is detected before drafting.
        self.assertEqual(len(seq.touch_ids), 5)

    @patch("requests.post")
    def test_stop_condition_checked_before_drafting(self, mock_post):
        mock_post.return_value = self._mock_response("should never be drafted")
        seq = self._make_seq()
        self.lead.write({"active": False})

        seq._process_one()

        mock_post.assert_not_called()
        self.assertEqual(seq.status, "stopped")
        self.assertEqual(len(seq.touch_ids), 0)
