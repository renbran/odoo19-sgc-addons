# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class CalendarAttendee(models.Model):
    _inherit = "calendar.attendee"

    def _send_invitation_emails(self):
        """Use the SGC-branded meeting invitation template if installed.

        The default calendar module ships ``calendar.calendar_template_meeting_invitation``
        which renders a fairly plain invitation. We ship a branded alternative
        (sgc_meeting_ai.mail_template_meeting_invitation_sgc) and prefer it here so
        every CRM/SDR invitation goes out with the SGC navy + gold styling and
        the videocall link rendered correctly (in concert with
        ``calendar_event._sgc_resend_meet_invitation`` which re-fires this hook
        once Google Calendar sync populates the real ``meet.google.com`` URL).
        Falls back to the upstream template if the SGC one is missing (e.g. on
        a fresh DB before the module has been upgraded).
        """
        sgc_template = self.env.ref(
            "sgc_meeting_ai.mail_template_meeting_invitation_sgc",
            raise_if_not_found=False,
        )
        if sgc_template:
            self._notify_attendees(sgc_template, force_send=True)
            return
        return super()._send_invitation_emails()