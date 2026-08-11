# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Widen the Google OAuth scope requested by google_calendar (core) so the
shared Meet organizer's connection can also manage Meet room access, not
just the calendar. Google refuses to grant meetings.space.settings unless
it is requested at consent time -- there is no per-call way to add it later
-- so this has to be in place *before* crm@sgctech.ai (re)connects.

Monkeypatching GoogleCalendarService instead of editing core: it's not an
Odoo model, so there is no ORM inheritance hook for it, and hand-editing
/usr/lib/python3/dist-packages/... would be wiped on the next image rebuild.
"""

import logging

from odoo.addons.google_calendar.utils.google_calendar import GoogleCalendarService

_logger = logging.getLogger(__name__)

_MEET_SCOPES = (
    " https://www.googleapis.com/auth/meetings.space.created"
    " https://www.googleapis.com/auth/meetings.space.settings"
)

_original_get_calendar_scope = GoogleCalendarService._get_calendar_scope


def _get_calendar_scope_with_meet(self, RO=False):
    scope = _original_get_calendar_scope(self, RO=RO)
    if RO:
        return scope
    return scope + _MEET_SCOPES


GoogleCalendarService._get_calendar_scope = _get_calendar_scope_with_meet
_logger.info("sgc_meeting_ai: patched GoogleCalendarService to request Meet space scopes")
