# Copyright 2025 SGC Tech AI
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SGCMeetingProvider(models.Model):
    """Meeting link provider configuration.

    Each provider represents a video/physical meeting platform that can be
    auto-assigned to bookings. Examples: Google Meet, Zoom, Microsoft Teams.
    """

    _name = "sgc.meeting.provider"
    _description = "SGC Meeting Provider"
    _order = "sequence, name"
    _rec_name = "name"

    name = fields.Char(required=True, translate=True)
    code = fields.Selection(
        [
            ("google_meet", "Google Meet"),
            ("zoom", "Zoom"),
            ("teams", "Microsoft Teams"),
            ("in_person", "In Person"),
            ("none", "None / Manual"),
        ],
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    icon = fields.Char(
        help="Font Awesome icon class (e.g. fa-google) used in kanban and buttons."
    )
    color = fields.Integer(string="Color Index")
    link_pattern = fields.Char(
        help="URL pattern for the meeting link. Use {meeting_id} as placeholder.",
    )
    description = fields.Html(string="Setup Instructions")
    webhook_url = fields.Char(
        compute="_compute_webhook_url",
        help="External bot service POSTs the meeting recording to this URL.",
    )
    webhook_token = fields.Char(
        groups="base.group_system",
        help="Shared secret used to authenticate webhook callbacks from bot service.",
    )
    session_count = fields.Integer(
        compute="_compute_session_count", string="Sessions"
    )
    notes_count = fields.Integer(compute="_compute_session_count", string="Notes")

    _sql_constraints = [
        ("code_unique", "UNIQUE(code)", "Provider code must be unique."),
    ]

    def _compute_webhook_url(self):
        base = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", default="http://localhost:8069")
        )
        for provider in self:
            provider.webhook_url = (
                f"{base}/sgc_meeting_ai/webhook/{provider.code}/upload"
            )

    def _compute_session_count(self):
        Session = self.env["sgc.meeting.session"].sudo()
        Notes = self.env["sgc.meeting.notes"].sudo()
        for provider in self:
            provider.session_count = Session.search_count(
                [("provider_id", "=", provider.id)]
            )
            provider.notes_count = Notes.search_count(
                [("provider_id", "=", provider.id)]
            )

    @api.constrains("code")
    def _check_code(self):
        valid_codes = {c[0] for c in self._fields["code"].selection}
        for provider in self:
            if provider.code not in valid_codes:
                raise ValidationError(
                    _(f"Invalid provider code: {provider.code}")
                )

    def action_open_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sessions — %s", self.name),
            "res_model": "sgc.meeting.session",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
        }

    def action_open_notes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Notes — %s", self.name),
            "res_model": "sgc.meeting.notes",
            "view_mode": "list,form",
            "domain": [("provider_id", "=", self.id)],
        }

    def regenerate_webhook_token(self):
        """Regenerate the webhook shared secret."""
        import secrets

        for provider in self:
            provider.webhook_token = secrets.token_urlsafe(32)
        return True
