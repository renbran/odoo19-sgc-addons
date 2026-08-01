# Copyright 2026 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Regression tests for the Google Meet booking chain.

These cover the pure, network-free logic that decides *whether* a meeting
gets routed to the shared Meet organizer, *whether* its Meet URL is captured,
and *whether* a silently-disabled sync gets repaired. The actual
``_google_insert`` call is not exercised — it talks to Google — but every
branch that historically failed silently around it is.

The bug these guard against produced no error at all: bookings simply never
reached Google, and the credential checks kept reporting healthy. So the
assertions are deliberately about the decisions, not about exceptions.
"""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestCustomerMeetingDetection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["calendar.event"]
        cls.customer = cls.env["res.partner"].create(
            {"name": "Acme Prospect", "email": "buyer@acme.example"}
        )
        cls.employee = cls.env["res.users"].create({
            "name": "Internal SDR",
            "login": "sgc_test_sdr",
            "email": "sdr@sgctech.example",
        })
        cls.portal_user = cls.env["res.users"].create({
            "name": "Portal Contact",
            "login": "sgc_test_portal",
            "email": "portal@acme.example",
            # Odoo 19 renamed res.users.groups_id -> group_ids.
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })

    def _make_event(self, partners, opportunity=None):
        vals = {
            "name": "Detection Test",
            "start": fields.Datetime.now(),
            "stop": fields.Datetime.now(),
            "partner_ids": [(6, 0, partners.ids)],
        }
        if opportunity:
            vals["opportunity_id"] = opportunity.id
        return self.Event.create(vals)

    def test_partner_without_user_account_is_a_customer_meeting(self):
        event = self._make_event(self.customer)
        self.assertTrue(event._sgc_is_customer_meeting())

    def test_portal_share_user_is_external_and_counts_as_customer(self):
        # A portal contact has a res.users row, so a naive "has a user account"
        # check would wrongly classify them as internal and skip the Meet room.
        event = self._make_event(self.portal_user.partner_id)
        self.assertTrue(event._sgc_is_customer_meeting())

    def test_internal_only_meeting_is_not_a_customer_meeting(self):
        event = self._make_event(self.employee.partner_id)
        self.assertFalse(event._sgc_is_customer_meeting())

    def test_meeting_with_no_attendees_is_not_a_customer_meeting(self):
        event = self._make_event(self.env["res.partner"])
        self.assertFalse(event._sgc_is_customer_meeting())

    def test_crm_opportunity_always_qualifies_even_if_all_attendees_internal(self):
        opportunity = self.env["crm.lead"].create(
            {"name": "Internal-attendee opportunity", "type": "opportunity"}
        )
        event = self._make_event(self.employee.partner_id, opportunity=opportunity)
        self.assertTrue(event._sgc_is_customer_meeting())

    def test_organizer_alone_does_not_make_it_a_customer_meeting(self):
        # The organizer is unioned into partner_ids by _sgc_apply_meet_organizer,
        # so counting them would make every meeting look external.
        event = self._make_event(self.env.user.partner_id)
        self.assertFalse(event._sgc_is_customer_meeting())


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestMeetUrlExtraction(TransactionCase):
    """Google returns the Meet room on the insert response. Upstream throws it
    away; capturing it is what turns a ~24h wait into seconds."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["calendar.event"]

    def test_extracts_hangout_link(self):
        url = self.Event._sgc_extract_meet_url(
            {"hangoutLink": "https://meet.google.com/abc-defg-hij"}
        )
        self.assertEqual(url, "https://meet.google.com/abc-defg-hij")

    def test_falls_back_to_conference_video_entry_point(self):
        url = self.Event._sgc_extract_meet_url({
            "conferenceData": {
                "entryPoints": [
                    {"entryPointType": "phone", "uri": "tel:+1-555-0100"},
                    {"entryPointType": "video", "uri": "https://meet.google.com/xyz-1234-abc"},
                ]
            }
        })
        self.assertEqual(url, "https://meet.google.com/xyz-1234-abc")

    def test_ignores_non_video_entry_points(self):
        url = self.Event._sgc_extract_meet_url({
            "conferenceData": {
                "entryPoints": [{"entryPointType": "phone", "uri": "tel:+1-555-0100"}]
            }
        })
        self.assertFalse(url)

    def test_handles_empty_and_missing_payloads(self):
        self.assertFalse(self.Event._sgc_extract_meet_url({}))
        self.assertFalse(self.Event._sgc_extract_meet_url(None))
        self.assertFalse(self.Event._sgc_extract_meet_url({"conferenceData": {}}))


@tagged("post_install", "-at_install", "sgc_meeting_ai")
class TestMeetOrganizerSyncSelfHeal(TransactionCase):
    """``google_synchronization_stopped`` silently removes the organizer from
    the sync cron's domain while the refresh token stays valid, so every
    credential check keeps passing. Repairing it must be automatic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizer = cls.env["res.users"].create({
            "name": "Meet Organizer",
            "login": "sgc_test_meet_organizer",
            "email": "meet-organizer@sgctech.example",
        })

    def test_self_heal_is_a_noop_without_google_calendar_installed(self):
        # The module does not depend on google_calendar, so the field may be
        # absent entirely. This must not raise.
        self.organizer._sgc_ensure_google_sync_enabled()

    def test_stopped_sync_is_re_enabled_when_a_token_is_present(self):
        if "google_synchronization_stopped" not in self.organizer._fields:
            self.skipTest("google_calendar is not installed")
        self.organizer.sudo().google_calendar_rtoken = "fake-refresh-token"
        self.organizer.sudo().google_synchronization_stopped = True

        self.organizer._sgc_ensure_google_sync_enabled()

        self.assertFalse(self.organizer.sudo().google_synchronization_stopped)

    def test_sync_is_left_alone_when_there_is_no_token(self):
        # Flipping the flag without a token would turn an honest "not
        # connected" state into a confusing "connected but failing" one.
        if "google_synchronization_stopped" not in self.organizer._fields:
            self.skipTest("google_calendar is not installed")
        self.organizer.sudo().google_calendar_rtoken = False
        self.organizer.sudo().google_synchronization_stopped = True

        self.organizer._sgc_ensure_google_sync_enabled()

        self.assertTrue(self.organizer.sudo().google_synchronization_stopped)
