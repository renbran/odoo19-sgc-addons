# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestRealSend(TransactionCase):
    """Exercises _send_whatsapp / _send_email directly against real
    whatsmeow.message / mail.mail creation -- not mocked, since the whole
    point is proving these calls satisfy whatsmeow's own constraints
    (_check_target_for_outgoing, _check_chat_is_sendable,
    _check_content_for_outgoing) and Odoo's own mail.mail requirements. No
    network call happens either way: creating the row is enough to prove
    correctness, the actual dispatch is whatsmeow's / Odoo's own
    already-tested queue crons, not this module's job to verify again.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        stage = cls.env["crm.stage"].create({"name": "Test Stage", "sequence": 1})
        cls.connection = cls.env["whatsmeow.connection"].create({
            "name": "Test Gateway",
            "base_url": "http://127.0.0.1:8080",
            "api_key": "test-key",
            "webhook_secret": "test-secret",
        })
        cls.session = cls.env["whatsmeow.session"].create({
            "name": "Test Session",
            "code": "test-session",
            "connection_id": cls.connection.id,
            "status": "connected",
        })

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Opportunity",
            "type": "opportunity",
            "stage_id": self.env["crm.stage"].search([], limit=1).id,
            "x_bant_budget": "b", "x_bant_authority": "a", "x_bant_need": "n",
            "phone": "+971501234567",
            "email_from": "test-lead@example.com",
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _make_seq(self, lead):
        return self.env["sgc.nurture.sequence"].create({
            "lead_id": lead.id, "status": "active", "dry_run": False,
        })

    def _make_touch(self, seq, channel, body="Hi there, following up on this."):
        return self.env["sgc.nurture.touch"].create({
            "sequence_id": seq.id, "touch_number": 1, "channel": channel,
            "body": body, "delivery_status": "drafted",
        })

    def test_send_whatsapp_creates_valid_message(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        touch = self._make_touch(seq, "whatsapp")

        seq._send_whatsapp(touch)

        self.assertTrue(touch.whatsmeow_message_id)
        message = touch.whatsmeow_message_id
        self.assertEqual(message.direction, "out")
        self.assertEqual(message.phone, "971501234567")
        self.assertEqual(message.body, touch.body)
        self.assertEqual(message.state, "outgoing")

    def test_send_whatsapp_no_phone_raises(self):
        lead = self._make_lead(phone=False, mobile=False)
        seq = self._make_seq(lead)
        touch = self._make_touch(seq, "whatsapp")
        with self.assertRaises(UserError):
            seq._send_whatsapp(touch)

    def test_send_email_creates_valid_mail(self):
        lead = self._make_lead()
        seq = self._make_seq(lead)
        touch = self._make_touch(seq, "email")

        seq._send_email(touch)

        self.assertTrue(touch.mail_message_id)
        mail = touch.mail_message_id
        self.assertEqual(mail.email_to, lead.email_from)
        self.assertIn(touch.body.split(".")[0], mail.body_html)

    def test_send_email_no_address_raises(self):
        lead = self._make_lead(email_from=False)
        seq = self._make_seq(lead)
        touch = self._make_touch(seq, "email")
        with self.assertRaises(UserError):
            seq._send_email(touch)

    def test_send_email_blacklisted_raises(self):
        lead = self._make_lead()
        self.env["mail.blacklist"].sudo()._add(lead.email_from)
        seq = self._make_seq(lead)
        touch = self._make_touch(seq, "email")
        with self.assertRaises(UserError):
            seq._send_email(touch)
