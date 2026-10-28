# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Never force a notification through an archived outgoing mail server.

        Some legacy flow stamps an explicit ``mail_server_id`` onto messages
        created by the public website user, and when that server has since been
        archived (e.g. the decommissioned "resend" relay) the send dies with
        ``The server "resend" cannot be used because it is archived`` and the
        invitation never reaches anybody. Drop the stale pin so the normal
        server auto-selection takes over at send time.
        """
        forced_ids = {
            vals["mail_server_id"]
            for vals in vals_list
            if vals.get("mail_server_id")
        }
        if forced_ids:
            inactive = (
                self.env["ir.mail_server"]
                .sudo()
                .browse(list(forced_ids))
                .filtered(lambda server: not server.active)
            )
            if inactive:
                _logger.warning(
                    "Dropping archived outgoing mail server(s) %s forced on "
                    "new mail.message records; falling back to automatic "
                    "server selection.",
                    ", ".join(inactive.mapped("display_name")),
                )
                inactive_ids = set(inactive.ids)
                for vals in vals_list:
                    if vals.get("mail_server_id") in inactive_ids:
                        vals["mail_server_id"] = False
        return super().create(vals_list)
