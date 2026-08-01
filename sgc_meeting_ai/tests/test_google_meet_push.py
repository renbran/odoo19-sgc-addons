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

from datetime import timedelta

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
class TestResourceBookingRecursion(TransactionCase):
    """resource.booking.start is a settable stored field, so a stray
    default_start in the context made _sync_meeting lazily create a second
    calendar.event, which re-entered create() and booked again. That loop
    produced triplicated meetings and a validation error listing the same
    booking three times."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create(
            {"name": "Recursion Test Customer", "email": "recursion@acme.example"}
        )
        cls.opportunity = cls.env["crm.lead"].create(
            {"name": "Recursion Test opportunity", "type": "opportunity"}
        )

    def _book(self, context=None):
        Event = self.env["calendar.event"]
        if context:
            Event = Event.with_context(**context)
        start = fields.Datetime.now() + timedelta(days=3)
        return Event.create({
            "name": "Recursion Test meeting",
            "start": start,
            "stop": start + timedelta(minutes=30),
            "partner_ids": [(6, 0, self.customer.ids)],
            "opportunity_id": self.opportunity.id,
        })

    def _events_named(self, name):
        return self.env["calendar.event"].search([("name", "=", name)])

    def test_booking_a_crm_meeting_creates_exactly_one_event(self):
        self._book()
        self.assertEqual(len(self._events_named("Recursion Test meeting")), 1)

    def test_a_stray_default_start_does_not_duplicate_the_meeting(self):
        # The exact trigger: booking from a view that leaves default_start in
        # the context. Before the fix this produced extra events and bookings.
        stray = fields.Datetime.now() + timedelta(days=3)
        self._book(context={"default_start": stray, "default_duration": 0.5})
        self.assertEqual(len(self._events_named("Recursion Test meeting")), 1)

    def test_booking_type_is_reachable_without_resource_booking_rights(self):
        """Registration is a side effect of saving a meeting, so it runs as
        whoever touches the event -- a salesperson, or crm@sgctech.ai when the
        Google sync writes back. Neither holds resource_booking rights.

        Without sudo this raised "Access Denied by ACLs for operation: read,
        uid: 111, model: resource.booking.type", which _sgc_register_meeting's
        try/except swallowed as a bare "Failed to create resource booking" --
        so bookings silently stopped being created and nobody noticed.

        Asserted at this level rather than through a full create() because
        upstream crm.log_meeting() posts to the opportunity's chatter first,
        so a restricted user trips CRM's own record rules long before reaching
        this code -- which would test Odoo's ACLs, not our sudo.
        """
        plain_user = self.env["res.users"].create({
            "name": "No Booking Rights",
            "login": "sgc_test_no_rights",
            "email": "norights@sgctech.example",
        })
        event = self.env["calendar.event"].browse()
        booking_type = event.with_user(plain_user)._get_or_create_booking_type()
        self.assertTrue(
            booking_type,
            "the booking type must be reachable without resource_booking rights",
        )

    def test_register_is_skipped_under_the_recursion_guard(self):
        event = self._book(context={"sgc_skip_meeting_register": True})
        self.assertFalse(
            event.sgc_booking_id,
            "sgc_skip_meeting_register must stop a resource_booking-spawned "
            "event from booking again",
        )


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
