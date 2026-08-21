# -*- coding: utf-8 -*-
from unittest.mock import Mock, patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestCadence(TransactionCase):
    """Drafting goes through llm.provider._make_request, which shells out
    via `requests.post` -- mocked here exactly the way sgc_lead_scoring's
    own tests mock it, so these never hit a real network/API. Sending is
    exercised through the sequence's `dry_run` override in most tests
    (draft/send/advance mechanics) and through the real whatsmeow.message /
    mail.mail creation paths in the two `TestRealSend*` classes below.
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

    def _make_seq(self, dry_run=True):
        return self.env["sgc.nurture.sequence"].create({
            "lead_id": self.lead.id, "status": "active", "dry_run": dry_run,
        })

    def _mock_response(self, text):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": [{"message": {"content": text}}]}
        return mock_response

    @patch("requests.post")
    def test_draft_then_send_first_touch(self, mock_post):
        mock_post.return_value = self._mock_response(
            "Hi there, just wanted to check in about your Odoo project. "
            "Happy to chat whenever suits you.")
        seq = self._make_seq()

        seq.action_draft_next_touch()
        touch = seq.touch_ids
        self.assertEqual(len(touch), 1)
        self.assertEqual(touch.channel, "whatsapp")
        self.assertEqual(touch.delivery_status, "drafted")
        self.assertEqual(seq.current_touch, 0, "drafting must not advance the counter")
        self.assertTrue(seq.has_pending_draft)

        seq.action_send_drafted_touch()
        self.assertEqual(seq.current_touch, 1)
        self.assertEqual(touch.delivery_status, "skipped_dry_run")
        self.assertFalse(seq.has_pending_draft)

    @patch("requests.post")
    def test_send_without_draft_raises(self, mock_post):
        seq = self._make_seq()
        with self.assertRaises(UserError):
            seq.action_send_drafted_touch()
        mock_post.assert_not_called()

    @patch("requests.post")
    def test_blocked_draft_cannot_be_sent(self, mock_post):
        mock_post.return_value = self._mock_response(
            "As an AI assistant, I guarantee this will work for you.")
        seq = self._make_seq()

        with self.assertRaises(UserError):
            seq.action_draft_next_touch()
        touch = seq.touch_ids
        self.assertEqual(touch.delivery_status, "validation_blocked")

        with self.assertRaises(UserError):
            seq.action_send_drafted_touch()
        self.assertEqual(seq.current_touch, 0)

    @patch("requests.post")
    def test_five_touches_then_exhausted(self, mock_post):
        mock_post.return_value = self._mock_response(
            "Just checking in -- still relevant for you? No pressure either way.")
        seq = self._make_seq()

        for _ in range(5):
            seq.action_draft_next_touch()
            seq.action_send_drafted_touch()

        self.assertEqual(seq.current_touch, 5)
        self.assertEqual(len(seq.touch_ids), 5)
        self.assertEqual(seq.status, "active")  # the 6th draft attempt is what flips it

        with self.assertRaises(UserError):
            seq.action_draft_next_touch()
        self.assertEqual(seq.status, "exhausted")
        self.assertEqual(seq.stop_event, "exhausted")
        self.assertEqual(len(seq.touch_ids), 5)

    @patch("requests.post")
    def test_stop_condition_checked_before_drafting(self, mock_post):
        mock_post.return_value = self._mock_response("should never be drafted")
        seq = self._make_seq()
        self.lead.write({"active": False})

        with self.assertRaises(UserError):
            seq.action_draft_next_touch()

        mock_post.assert_not_called()
        self.assertEqual(seq.status, "stopped")
        self.assertEqual(len(seq.touch_ids), 0)

    @patch("requests.post")
    def test_stop_condition_checked_before_sending(self, mock_post):
        """A lead can close in the gap between drafting and a person
        clicking send -- must not send in that case.
        """
        mock_post.return_value = self._mock_response("Hi there, checking in.")
        seq = self._make_seq()
        seq.action_draft_next_touch()

        self.lead.write({"active": False})
        with self.assertRaises(UserError):
            seq.action_send_drafted_touch()
        self.assertEqual(seq.status, "stopped")
        self.assertEqual(seq.current_touch, 0)
