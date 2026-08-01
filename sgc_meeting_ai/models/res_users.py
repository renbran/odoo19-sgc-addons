# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    def _sgc_ensure_google_sync_enabled(self):
        """Keep the shared Meet organizer's Google synchronization switched on.

        ``google_synchronization_stopped`` is a plain boolean set by the "Stop
        Synchronization" button. While it is True the account is dropped from
        the sync cron's domain outright (see
        ``google_calendar/models/res_users.py::_sync_all_google_calendar``), so
        *nothing* reaches Google: no calendar entry, no Meet room, and no
        invitation carrying a link. Meanwhile the refresh token stays perfectly
        valid, so every credential check -- including
        ``/opt/odoo-prod/sgc_healthcheck.sh`` -- keeps reporting healthy. That
        combination is invisible from the outside and cost a full debugging
        session to find.

        So rather than merely reporting it, repair it. The Meet organizer is a
        dedicated service account whose only purpose is to hold the Google
        connection on behalf of the sales team; sync being off is always a
        misconfiguration, never an intentional state. Repairing on every
        booking (rather than once at install) means the fix also survives a
        database restore, a module upgrade, or somebody clicking the button
        again.

        The database-wide ``google_calendar_sync_paused`` parameter is
        deliberately NOT touched: that one *is* an intentional kill switch.
        """
        for user in self:
            if "google_synchronization_stopped" not in user._fields:
                continue  # google_calendar is not installed
            user_sudo = user.sudo()
            # Without a token there is nothing to re-enable, and flipping the
            # flag would only turn a clear "not connected" state into a
            # confusing "connected but failing" one.
            if not user_sudo.google_calendar_rtoken:
                continue
            if not user_sudo.google_synchronization_stopped:
                continue
            user_sudo.google_synchronization_stopped = False
            _logger.warning(
                "Google Calendar synchronization was switched off for the "
                "shared Meet organizer %s; re-enabling it. Any meeting booked "
                "while it was off never reached Google and therefore has no "
                "Meet link -- those need to be re-sent by hand.",
                user.login,
            )
