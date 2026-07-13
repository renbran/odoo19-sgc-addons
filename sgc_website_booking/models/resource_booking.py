# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResourceBooking(models.Model):
    _inherit = 'resource.booking'

    # Flag bookings that originated from the public /book-session page so the
    # auto-response cron only emails website requesters (not backend bookings).
    sgc_web_booking = fields.Boolean(
        string='Website Booking', default=False, copy=False, index=True,
    )
    sgc_confirm_email_sent = fields.Boolean(
        string='Confirmation Emailed', default=False, copy=False,
    )
    sgc_fail_email_sent = fields.Boolean(
        string='Failure Notice Emailed', default=False, copy=False,
    )

    def _sgc_requester_email(self):
        """Best email for the booking requester."""
        self.ensure_one()
        partner = self.partner_id or self.partner_ids[:1]
        return partner.email

    @api.model
    def _cron_send_booking_responses(self):
        """Send success / failure auto-responses for website bookings.

        Success: confirmed (or scheduled) website bookings not yet emailed.
        Failure: website bookings that were cancelled / unscheduled, or whose
        AI notetaker session reached the 'failed' state.
        """
        confirmed_tmpl = self.env.ref(
            'sgc_website_booking.mail_template_booking_confirmed',
            raise_if_not_found=False)
        failed_tmpl = self.env.ref(
            'sgc_website_booking.mail_template_booking_failed',
            raise_if_not_found=False)

        Booking = self.with_context(active_test=False)

        # ---- Success confirmations ----
        if confirmed_tmpl:
            to_confirm = Booking.search([
                ('sgc_web_booking', '=', True),
                ('sgc_confirm_email_sent', '=', False),
                ('active', '=', True),
                ('state', 'in', ['scheduled', 'confirmed']),
            ])
            for booking in to_confirm:
                if not booking._sgc_requester_email():
                    continue
                try:
                    confirmed_tmpl.send_mail(booking.id, force_send=False)
                    booking.sgc_confirm_email_sent = True
                except Exception:
                    _logger.exception(
                        "Booking confirmation email failed for booking %s",
                        booking.id)

        # ---- Failure / cancellation notices ----
        if failed_tmpl:
            failed = Booking.search([
                ('sgc_web_booking', '=', True),
                ('sgc_fail_email_sent', '=', False),
                '|',
                    ('state', 'in', ['canceled', 'pending']),
                    ('meeting_id.sgc_session_id.state', '=', 'failed'),
            ])
            for booking in failed:
                if not booking._sgc_requester_email():
                    continue
                try:
                    failed_tmpl.send_mail(booking.id, force_send=False)
                    booking.sgc_fail_email_sent = True
                except Exception:
                    _logger.exception(
                        "Booking failure email failed for booking %s",
                        booking.id)
