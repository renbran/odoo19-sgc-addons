# -*- coding: utf-8 -*-
"""Public "Book an Online Session" controller.

Reuses the ``resource_booking`` availability engine for the calendar and wires a
confirmed booking to a CRM lead + an SGC Meeting AI notetaker session.
"""
import json
import logging
from datetime import datetime

from dateutil.parser import isoparse

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class SGCWebsiteBooking(http.Controller):

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #
    def _json(self, payload, status=200):
        return Response(
            json.dumps(payload),
            status=status,
            content_type='application/json; charset=utf-8',
        )

    def _get_active_type(self):
        """Return the configured public booking type (or a sane fallback)."""
        params = request.env['ir.config_parameter'].sudo()
        type_id = params.get_param('sgc_website_booking.type_id')
        Type = request.env['resource.booking.type'].sudo()
        booking_type = Type.browse(int(type_id)) if type_id else Type
        if not booking_type.exists():
            booking_type = request.env.ref(
                'sgc_website_booking.online_session_type',
                raise_if_not_found=False,
            )
        return booking_type

    def _new_booking(self, booking_type):
        """A transient (unsaved) booking used only to compute available slots."""
        tz = booking_type.resource_calendar_id.tz or 'UTC'
        return request.env['resource.booking'].sudo().with_context(
            using_portal=True, tz=tz,
        ).new({
            'type_id': booking_type.id,
            'duration': booking_type.duration,
        })

    # ------------------------------------------------------------------ #
    #  Page                                                               #
    # ------------------------------------------------------------------ #
    @http.route('/book-session', type='http', auth='public', website=True, sitemap=True)
    def book_session_page(self, **kwargs):
        booking_type = self._get_active_type()
        return request.render('sgc_website_booking.sgc_book_session', {
            'booking_type': booking_type,
        })

    # ------------------------------------------------------------------ #
    #  Slots (calendar data)                                              #
    # ------------------------------------------------------------------ #
    @http.route('/book-session/slots', type='http', auth='public',
                methods=['POST'], website=True, csrf=False)
    def book_session_slots(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or kwargs
        booking_type = self._get_active_type()
        if not booking_type:
            return self._json({'success': False,
                               'error': 'Online booking is not configured.'}, status=400)
        try:
            year = int(payload.get('year')) if payload.get('year') else None
            month = int(payload.get('month')) if payload.get('month') else None
        except (ValueError, TypeError):
            year = month = None

        booking = self._new_booking(booking_type)
        ctx = booking._get_calendar_context(year, month)
        raw_slots = ctx['slots']  # {date: [tz-aware datetime, ...]}

        slots = {}
        for day, times in raw_slots.items():
            slots[day.isoformat()] = [
                {'iso': t.isoformat(), 'label': t.strftime('%H:%M')}
                for t in times
            ]
        start = ctx['start']
        return self._json({
            'success': True,
            'year': start.year,
            'month': start.month,
            'tz': booking_type.resource_calendar_id.tz or 'UTC',
            'duration': booking_type.duration,
            'slots': slots,
        })

    # ------------------------------------------------------------------ #
    #  Confirm                                                            #
    # ------------------------------------------------------------------ #
    @http.route('/book-session/confirm', type='http', auth='public',
                methods=['POST'], website=True, csrf=False)
    def book_session_confirm(self, **kwargs):
        payload = request.httprequest.get_json(silent=True) or kwargs
        name = (payload.get('name') or '').strip()
        email = (payload.get('email') or '').strip()
        phone = (payload.get('phone') or '').strip()
        when = (payload.get('when') or '').strip()
        topic = (payload.get('topic') or '').strip()
        notes = (payload.get('notes') or '').strip()

        if not name or not email or not when:
            return self._json({'success': False,
                               'error': 'Name, email and a time slot are required.'},
                              status=400)
        if '@' not in email or '.' not in email.split('@')[-1]:
            return self._json({'success': False,
                               'error': 'Please enter a valid email address.'}, status=400)

        booking_type = self._get_active_type()
        if not booking_type:
            return self._json({'success': False,
                               'error': 'Online booking is not configured.'}, status=400)

        env = request.env
        tz = booking_type.resource_calendar_id.tz or 'UTC'

        # Parse the requested slot (same ISO -> naive UTC conversion as the portal).
        try:
            when_tz_aware = isoparse(when)
        except (ValueError, TypeError):
            return self._json({'success': False,
                               'error': 'Invalid time slot.'}, status=400)
        when_naive = datetime.utcfromtimestamp(when_tz_aware.timestamp())

        # 0) Pre-check availability against the real slot engine BEFORE creating
        # any records, so a taken/expired slot returns a clean 409 (and we never
        # leave an orphan partner/lead/booking behind).
        probe = self._new_booking(booking_type)
        ctx = probe._get_calendar_context(when_tz_aware.year, when_tz_aware.month)
        day_slots = ctx['slots'].get(when_tz_aware.date(), [])
        if not any(abs((s - when_tz_aware).total_seconds()) < 60 for s in day_slots):
            return self._json({
                'success': False,
                'error': 'That time slot is no longer available. Please pick another.',
            }, status=409)

        # 1) Find-or-create partner by email
        Partner = env['res.partner'].sudo()
        partner = Partner.search([('email', '=ilike', email)], limit=1)
        if not partner:
            partner = Partner.create({
                'name': name,
                'email': email,
                'phone': phone or False,
            })

        # 2) CRM lead for follow-up
        description = []
        if topic:
            description.append('Session topic: %s' % topic)
        if notes:
            description.append('Notes: %s' % notes)
        description.append('Requested slot: %s' % when)
        # Include the company (partner) name so the lead is findable by the
        # account name too, not only by the person who filled the form.
        lead_title = 'Online Session: %s' % name
        if partner.name and partner.name != name:
            lead_title = 'Online Session: %s - %s' % (partner.name, name)
        lead = env['crm.lead'].sudo().create({
            'name': lead_title,
            'contact_name': name,
            'partner_id': partner.id,
            'email_from': email,
            'phone': phone or False,
            'type': 'lead',
            'description': '\n'.join(description),
        })

        # 3) Resource booking (reuses the slot engine for validation)
        Booking = env['resource.booking'].sudo().with_context(using_portal=True, tz=tz)
        # Route the meeting through the shared Meet organizer up front: the
        # invitation sender then renders as the CRM identity instead of the
        # anonymous website user (which used to emit invites with an empty
        # From:), and the organizer no longer has to be reassigned after the
        # fact -- one less write that re-notified every attendee.
        organizer_login = env['ir.config_parameter'].sudo().get_param(
            'sgc_meeting_ai.meet_organizer_login')
        organizer = env['res.users'].sudo().search(
            [('login', '=', organizer_login)], limit=1) if organizer_login else False
        booking_vals = {
            'type_id': booking_type.id,
            'partner_ids': [(6, 0, [partner.id])],
            'sgc_web_booking': True,
            # Explicit name so bookings are searchable in the backend lists
            # ("I S P R ...", "Boshra", ...) instead of a blank row.
            'name': '%s - %s' % (partner.name or name, booking_type.name),
        }
        if organizer:
            booking_vals['user_id'] = organizer.id
        booking = Booking.create(booking_vals)

        # 4) Apply chosen slot + confirm. The pre-check above handles the common
        # case; this guard is the backstop for a rare race (two requests for the
        # same slot in the same instant) and rolls back the empty booking.
        try:
            booking.start = when_naive
            booking.action_confirm()
            # Force deferred @api.constrains (_check_scheduling) to run *here*
            # so a slot clash is caught and returns a clean 409 instead of a
            # 422 page raised later at request-commit flush time.
            booking.flush_recordset()
        except ValidationError as error:
            booking.unlink()
            return self._json({
                'success': False,
                'error': error.args[0] if error.args else
                         'That time slot is no longer available. Please pick another.',
            }, status=409)

        # 5) Wire CRM lead and AI notetaker to the meeting
        meeting = booking.meeting_id
        if meeting:
            # Set sgc_booking_id so the sgc_meeting_ai write-hook does NOT spawn a
            # duplicate booking; link the opportunity for follow-up.
            meeting.write({
                'opportunity_id': lead.id,
                'sgc_booking_id': booking.id,
            })
            try:
                meeting._sgc_get_or_create_session(bot_enabled=True)
            except Exception:
                _logger.exception(
                    "Failed to attach AI session to meeting %s", meeting.id)

        return self._json({
            'success': True,
            'message': 'Your session is booked! A confirmation with the meeting '
                       'link will be emailed to %s shortly.' % email,
            'booking_url': booking.get_portal_url(),
        })
