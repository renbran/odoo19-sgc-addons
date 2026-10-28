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

    def _notify_attendees(self, mail_template, notify_author=False, force_send=False):
        """Keep ONE invitation style, even for attendees added after creation.

        Core ``calendar.event.write`` notifies newly added attendees with the
        plain ``calendar.calendar_template_meeting_invitation`` directly, which
        bypasses the ``_send_invitation_emails`` override above: a single
        booking then produces both "Invitation · ..." (branded) and
        "Invitation to ..." (plain) mails. Swap the plain invitation for the
        SGC one here so every attendee only ever sees the branded invite.
        """
        sgc_template = self.env.ref(
            "sgc_meeting_ai.mail_template_meeting_invitation_sgc",
            raise_if_not_found=False,
        )
        plain_invite = self.env.ref(
            "calendar.calendar_template_meeting_invitation",
            raise_if_not_found=False,
        )
        if sgc_template and mail_template == plain_invite:
            mail_template = sgc_template
        return super()._notify_attendees(
            mail_template, notify_author=notify_author, force_send=force_send
        )

    def _compute_mail_tz(self):
        """Render invitation times in the meeting's operating timezone.

        Core only uses the attendee partner's own timezone, so a customer
        contact without one gets the time rendered in UTC while the internal
        copies show Dubai time -- the same meeting then arrived labelled
        "11:30" in one inbox and "15:30" in another. Fall back to the
        organizer's timezone so every copy agrees.
        """
        super()._compute_mail_tz()
        for attendee in self:
            if not attendee.mail_tz:
                attendee.mail_tz = (
                    attendee.event_id.user_id.tz
                    or self.env.context.get("tz")
                    or self.env.user.tz
                )
