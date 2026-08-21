# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestStopMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_open = cls.env["crm.stage"].create({"name": "Test Open", "sequence": 1})
        cls.stage_won = cls.env["crm.stage"].create(
            {"name": "Test Won", "sequence": 9, "is_won": True})

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": self.stage_open.id,
            "x_bant_budget": "b", "x_bant_authority": "a", "x_bant_need": "n",
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _make_seq(self, lead, status="active"):
        return self.env["sgc.nurture.sequence"].create({
            "lead_id": lead.id, "status": status,
        })

    def test_lost_lead_stops_with_lost_event(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        lead.write({"active": False})

        should_stop, reason, event = seq._evaluate_stop_conditions()
        self.assertTrue(should_stop)
        self.assertEqual(event, "lost")

    def test_won_stage_stops_with_won_event(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        lead.write({"stage_id": self.stage_won.id})

        should_stop, reason, event = seq._evaluate_stop_conditions()
        self.assertTrue(should_stop)
        self.assertEqual(event, "won")

    def test_open_lead_does_not_stop(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        should_stop, reason, event = seq._evaluate_stop_conditions()
        self.assertFalse(should_stop)

    def test_apply_stop_won_sets_status_stopped(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        seq._apply_stop("Marked Won.", "won")
        self.assertEqual(seq.status, "stopped")
        self.assertFalse(seq.next_touch_at)

    def test_apply_stop_reply_sets_status_responded_and_creates_activity(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        before = self.env["mail.activity"].search_count([
            ("res_model", "=", "crm.lead"), ("res_id", "=", lead.id),
        ])
        seq._apply_stop("Lead replied on WhatsApp.", "wa_reply")
        self.assertEqual(seq.status, "responded")
        after = self.env["mail.activity"].search_count([
            ("res_model", "=", "crm.lead"), ("res_id", "=", lead.id),
        ])
        self.assertEqual(after, before + 1)

    def test_manual_pause_and_resume(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        seq.action_pause(reason="testing")
        self.assertEqual(seq.status, "paused")
        self.assertEqual(seq.pause_reason, "testing")

        seq.action_resume()
        self.assertEqual(seq.status, "active")
        self.assertFalse(seq.pause_until)
        self.assertTrue(seq.next_touch_at)

    def test_manual_stop(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        seq.action_stop("manager call")
        self.assertEqual(seq.status, "stopped")
        self.assertEqual(seq.stop_event, "manual_stop")

    def test_email_reply_hook_stops_sequence(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        lead._sgc_nurture_on_message_received()
        self.assertEqual(seq.status, "responded")
        self.assertEqual(seq.stop_event, "email_reply")

    def test_meeting_booked_hook_stops_sequence(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        lead._sgc_nurture_on_meeting_booked()
        self.assertEqual(seq.status, "responded")
        self.assertEqual(seq.stop_event, "meeting_booked")
