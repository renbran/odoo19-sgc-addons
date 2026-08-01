# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _calendar_event_busy_intervals(
        self, start_dt, end_dt, resource, analyzed_booking_id
    ):
        """Don't let the shared Meet organizer count as a busy person.

        resource_booking marks a resource busy for any overlapping event whose
        user is the organizer *or merely an undeclined attendee*. That is right
        for a real salesperson, but crm@sgctech.ai is a technical proxy: it is
        deliberately made organizer-and-attendee of every customer meeting so
        google_calendar's sync domain picks them up (see
        ``calendar_event._sgc_apply_meet_organizer``). Left alone, that account
        accumulates a busy interval for *every meeting in the database* and its
        resource becomes a company-wide bottleneck that can only ever hold one
        booking at a time -- surfacing as "Cannot schedule these bookings ...
        because all resources are busy" on meetings that have no real conflict.

        Its calendar has no finite capacity to protect, so it is skipped
        entirely. Every other resource keeps the normal conflict checks.
        """
        organizer_login = self.env["ir.config_parameter"].sudo().get_param(
            "sgc_meeting_ai.meet_organizer_login"
        )
        if organizer_login and resource and resource.sudo().user_id.login == organizer_login:
            _logger.debug(
                "Skipping busy-interval check for shared Meet organizer "
                "resource %s (%s)", resource.id, organizer_login,
            )
            # Handing super() an empty resource makes it take its own
            # short-circuit and return no busy intervals, which keeps this
            # override free of resource_booking's private Intervals import.
            resource = self.env["resource.resource"]
        return super()._calendar_event_busy_intervals(
            start_dt, end_dt, resource, analyzed_booking_id
        )
