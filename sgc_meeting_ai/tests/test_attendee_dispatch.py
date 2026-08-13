# Copyright 2026 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Regression tests for AI notetaker scheduling.

The bug these pin down: sessions are created when a meeting is *booked*, but
the bot was dispatched with no ``join_at``, so Attendee sent it into the room
immediately — days early — where it was denied entry and died with
``fatal_error``. Meanwhile every session booked before its Google Meet link had
synced was latched ``bot_dispatched = True`` behind a ``sgc-pending-``
placeholder and was never retried, so no bot was ever created at all.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import requests

from odoo import fields
from odoo.addons.sgc_meeting_ai.services.attendee_service import PLACEHOLDER_PREFIX
from odoo.tests import TransactionCase, tagged

_SERVICE = "odoo.addons.sgc_meeting_ai.services.attendee_service"


def _parse_iso(value):
    """Attendee speaks ISO 8601 with a 'T' and a 'Z'; fields.Datetime does not."""
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestAttendeeDispatch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env.ref("sgc_meeting_ai.sgc_provider_google_meet")
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_meeting_ai.attendee_api_key", "test-key"
        )

    def _make_session(self, days_ahead=7, link="https://meet.google.com/abc-defg-hij"):
        start = fields.Datetime.now() + timedelta(days=days_ahead)
        event = self.env["calendar.event"].create({
            "name": "Test Meeting",
            "start": start,
            "stop": start + timedelta(hours=1),
            "videocall_location": link,
        })
        return self.env["sgc.meeting.session"].create({
            "meeting_id": event.id,
            "provider_id": self.provider.id,
            "bot_enabled": True,
        })

    # ── join_at ───────────────────────────────────────────────────────────

    def test_create_bot_schedules_at_meeting_start_not_now(self):
        """The bot must be scheduled for the meeting, not for booking time."""
        session = self._make_session(days_ahead=7)
        captured = {}

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["json"] = kwargs.get("json")
            return {"id": "bot_test123", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.attendee.service"].create_bot(session)

        payload = captured["json"]
        self.assertIn(
            "join_at", payload,
            "join_at missing: Attendee would send the bot in immediately.",
        )
        join_at = _parse_iso(payload["join_at"])
        # Within a couple of minutes of the meeting start, i.e. a week out.
        self.assertLess(abs((join_at - session.start).total_seconds()), 180)
        self.assertGreater(
            (join_at - fields.Datetime.now()).total_seconds(), 6 * 24 * 3600,
            "Bot scheduled for booking time instead of meeting time.",
        )

    def test_join_at_for_imminent_meeting_is_pushed_into_the_future(self):
        """Attendee rejects a join_at in the past; a late booking still works."""
        session = self._make_session(days_ahead=0)
        session.meeting_id.write({
            "start": fields.Datetime.now() - timedelta(minutes=10),
            "stop": fields.Datetime.now() + timedelta(minutes=30),
        })
        join_at = self.env["sgc.meeting.attendee.service"].compute_join_at(session)
        self.assertGreater((join_at - fields.Datetime.now()).total_seconds(), 60)

    def test_deduplication_key_is_stable_per_session(self):
        session = self._make_session()
        captured = {}

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            captured["json"] = kwargs.get("json")
            return {"id": "bot_test123", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.attendee.service"].create_bot(session)
        self.assertEqual(
            captured["json"]["deduplication_key"], f"odoo-session-{session.id}"
        )

    # ── retry when the Meet link is not there yet ─────────────────────────

    def test_dispatch_without_link_stays_retryable(self):
        """No Meet link yet must not permanently retire the session."""
        session = self._make_session(link=False)
        session.action_dispatch_bot()
        self.assertFalse(
            session.bot_dispatched,
            "bot_dispatched latched with no link: the bot is never scheduled.",
        )
        self.assertFalse(session.bot_id)
        self.assertTrue(session.state_message)

    def test_cron_dispatches_once_the_link_arrives(self):
        session = self._make_session(link=False)
        session.action_dispatch_bot()
        self.assertFalse(session.bot_dispatched)

        # google_calendar syncs the real Meet room back a few minutes later.
        session.meeting_id.videocall_location = "https://meet.google.com/xyz-abcd-efg"

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            return {"id": "bot_late456", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.session"]._cron_dispatch_due_bots()

        self.assertTrue(session.bot_dispatched)
        self.assertEqual(session.bot_id, "bot_late456")
        self.assertTrue(session.bot_join_at)

    def test_cron_heals_legacy_placeholder_sessions(self):
        """Sessions retired by the old placeholder behaviour must recover."""
        session = self._make_session()
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": "sgc-pending-deadbeef",
        })

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            return {"id": "bot_healed789", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.session"]._cron_dispatch_due_bots()

        self.assertEqual(session.bot_id, "bot_healed789")

    def test_cron_rearms_a_bot_that_died_before_a_future_meeting(self):
        """A bot killed by the early-join bug must not cost the meeting its
        notetaker: the meeting has not happened yet, so try again."""
        session = self._make_session(days_ahead=5)
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": "bot_dead1",
            "bot_state": "fatal_error",
            "state": "failed",
            "state_message": "Attendee bot failed (state=fatal_error)",
        })

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            return {"id": "bot_rearm999", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.session"]._cron_dispatch_due_bots()

        self.assertEqual(session.bot_id, "bot_rearm999")
        self.assertEqual(session.state, "scheduled")
        self.assertFalse(session.state_message)

    def test_cron_leaves_a_past_failed_meeting_alone(self):
        """Don't send a bot to a meeting that already happened."""
        session = self._make_session(days_ahead=5)
        session.meeting_id.write({
            "start": fields.Datetime.now() - timedelta(days=2),
            "stop": fields.Datetime.now() - timedelta(days=2) + timedelta(hours=1),
        })
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": "bot_old1",
            "bot_state": "fatal_error",
            "state": "failed",
        })
        # The cron sweeps every session in the database, so assert on this
        # session specifically rather than on a global call count.
        dedup_keys = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            payload = kwargs.get("json") or {}
            dedup_keys.append(payload.get("deduplication_key"))
            return {"id": "bot_nope", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.session"]._cron_dispatch_due_bots()

        self.assertNotIn(f"odoo-session-{session.id}", dedup_keys)
        self.assertEqual(session.bot_id, "bot_old1")
        self.assertEqual(session.state, "failed")

    def test_poller_ignores_placeholder_bot_ids(self):
        session = self._make_session()
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": "sgc-pending-deadbeef",
        })
        calls = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            calls.append(path)
            return {"id": "x", "state": "ended"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            self.env["sgc.meeting.session"]._cron_poll_attendee_bots()
        # Other sessions in the database may legitimately be polled; what must
        # never happen is a call carrying a placeholder id.
        self.assertFalse(
            [p for p in calls if PLACEHOLDER_PREFIX in p],
            "Poller called Attendee with a placeholder id.",
        )

    # ── cancellation ──────────────────────────────────────────────────────

    def _dispatched_session(self, bot_id="bot_cancel1"):
        session = self._make_session(days_ahead=7)
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": bot_id,
            "bot_join_at": session.start,
        })
        return session

    def test_cancelling_the_meeting_cancels_the_bot(self):
        session = self._dispatched_session()
        calls = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            calls.append((method, path))
            return {}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.meeting_id.write({"active": False})

        self.assertIn(
            ("DELETE", "/api/v1/bots/bot_cancel1"), calls,
            "Cancelling the meeting left the bot scheduled to join.",
        )
        self.assertFalse(session.bot_dispatched)
        self.assertFalse(session.bot_id)

    def test_deleting_the_meeting_cancels_the_bot(self):
        session = self._dispatched_session(bot_id="bot_del1")
        calls = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            calls.append((method, path))
            return {}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.meeting_id.unlink()

        self.assertIn(("DELETE", "/api/v1/bots/bot_del1"), calls)

    def test_switching_the_bot_off_cancels_it(self):
        session = self._dispatched_session(bot_id="bot_off1")
        calls = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            calls.append((method, path))
            return {}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.meeting_id.write({"sgc_bot_enabled": False})

        self.assertIn(("DELETE", "/api/v1/bots/bot_off1"), calls)

    def test_restoring_a_cancelled_meeting_re_arms_the_bot(self):
        session = self._dispatched_session(bot_id="bot_restore1")

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            return {"id": "bot_rearmed", "state": "scheduled"}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.meeting_id.write({"active": False})
            self.assertFalse(session.bot_dispatched)
            session.meeting_id.write({"active": True})

        self.assertTrue(session.bot_dispatched)
        self.assertEqual(session.bot_id, "bot_rearmed")

    def test_cancel_falls_back_to_leave_when_delete_is_refused(self):
        """A bot already in the room cannot be deleted — make it leave."""
        session = self._dispatched_session(bot_id="bot_live1")
        calls = []

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            calls.append((method, path))
            if method == "DELETE":
                raise requests.HTTPError("400 bot already started")
            return {}

        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.cancel_bot(reason="test")

        self.assertIn(("POST", "/api/v1/bots/bot_live1/leave"), calls)

    def test_cancelling_a_session_without_a_bot_is_harmless(self):
        session = self._make_session()
        session.cancel_bot(reason="test")
        self.assertFalse(session.bot_dispatched)

    # ── reschedule ────────────────────────────────────────────────────────

    def test_moving_the_meeting_reschedules_the_bot(self):
        session = self._make_session(days_ahead=7)
        session.sudo().write({
            "bot_dispatched": True,
            "bot_id": "bot_move123",
            "bot_join_at": session.start,
        })
        captured = {}

        def fake_request(self_svc, method, path, cfg=None, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["json"] = kwargs.get("json")
            return {}

        new_start = fields.Datetime.now() + timedelta(days=9)
        with patch(f"{_SERVICE}.SGCMeetingAttendeeService._request", fake_request):
            session.meeting_id.write({
                "start": new_start,
                "stop": new_start + timedelta(hours=1),
            })

        self.assertEqual(captured.get("method"), "PATCH")
        self.assertEqual(captured.get("path"), "/api/v1/bots/bot_move123")
        join_at = _parse_iso(captured["json"]["join_at"])
        self.assertLess(abs((join_at - new_start).total_seconds()), 180)
