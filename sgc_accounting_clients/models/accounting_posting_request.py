# -*- coding: utf-8 -*-
"""Posting requests for drafts booked in a client database.

The accounting agents live in the CLIENT database: the intake agent creates
the draft there, and the posting agent may only post it once a manager has
approved a posting request - the guard on ``account.move.action_post`` in
the client database refuses anything else. This module is the agency-side
driver that carries that sequence:

1. ``_cron_request_approvals`` finds the drafts a booking created and asks
   the intake agent - in the client database - to open a posting request.
2. ``action_approve`` is the human step: an agency manager clicks it, and the
   manager's own key approves the request in the client database. A draft
   above the posting role's auto-post ceiling needs the explicit over-limit
   authorisation.
3. ``action_post`` then has the posting agent post the approved draft. The
   guard re-checks the approval and the ceiling, so a request that was never
   approved cannot be posted.

Every step is recorded here and in the client database's own agent audit
trail, so who approved what is never in doubt.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .accounting_client import rpc, rpc_error

_logger = logging.getLogger(__name__)

INTAKE_ROLE = "agent-01-intake"
MANAGER_ROLE = "agency-manager"
POSTING_ROLE = "agent-02-posting"

# The model a booking created in the client database.
DRAFT_MODEL = "account.move"
# The posting request in the client database.
APPROVAL_MODEL = "sgc.agent.posting.approval"


class SgcAccountingPostingRequest(models.Model):
    """A draft in a client database waiting for a posting decision."""

    _name = "sgc.accounting.posting.request"
    _description = "Accounting Posting Request"
    _order = "requested_at desc, id desc"
    _rec_name = "move_name"

    client_id = fields.Many2one(
        "sgc.accounting.client", required=True, ondelete="cascade", index=True,
    )
    upload_id = fields.Many2one(
        "sgc.accounting.upload", required=True, ondelete="cascade", index=True,
    )
    move_id = fields.Integer(
        required=True, help="The id of the draft in the client database.",
    )
    move_name = fields.Char(string="Draft")
    amount = fields.Float(string="Amount", readonly=True)
    currency = fields.Char(readonly=True)
    state = fields.Selection(
        [
            ("pending", "Waiting for approval"),
            ("approved", "Approved"),
            ("posted", "Posted"),
            ("refused", "Refused"),
            ("failed", "Failed"),
        ],
        default="pending", required=True, index=True, tracking=True,
    )
    approval_id = fields.Integer(
        help="The id of the posting request in the client database.",
        readonly=True,
    )
    over_limit = fields.Boolean(
        help="The draft is above the posting role's auto-post ceiling, so the "
             "manager must authorise it explicitly.",
        readonly=True,
    )
    attempts = fields.Integer(default=0)
    last_error = fields.Text(readonly=True)
    requested_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    approved_at = fields.Datetime(readonly=True)
    posted_at = fields.Datetime(readonly=True)

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------
    def _conn_for(self, role_code):
        """Return the connection for ``role_code`` against this client.

        The intake role is reached through the client's own booking
        connection, which is already validated to be this client's intake key.
        The other roles have their own per-client key file.
        """
        if role_code == INTAKE_ROLE:
            return self.client_id._booking_connection()
        return self.client_id._role_connection(role_code)

    def _open_approval(self):
        """Ask the intake agent to open a posting request in the client database."""
        self.ensure_one()
        conn, error = self._conn_for(INTAKE_ROLE)
        if error:
            self.write({"state": "failed", "last_error": error})
            return False
        try:
            approval_id = rpc(
                conn, APPROVAL_MODEL, "create", {
                    "name": _("Posting request for %(move)s",
                              move=self.move_name or self.move_id),
                    "move_id": self.move_id,
                    "agent_run_id": str(self.upload_id.id),
                    "source_sha256": self.upload_id.sha256 or False,
                    "state": "pending",
                },
            )
        except Exception as exc:
            self.write({
                "attempts": (self.attempts or 0) + 1,
                "state": "failed",
                "last_error": rpc_error(exc),
            })
            return False
        self.write({
            "approval_id": approval_id,
            "attempts": (self.attempts or 0) + 1,
            "last_error": False,
        })
        return True

    def action_approve(self):
        """Approve the posting request with the agency manager's own key.

        This is the human step: it only runs when a manager clicks it, and the
        approval lands in the client database under the manager's identity.
        """
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("Only a waiting request can be approved."))
        if not self.approval_id:
            raise UserError(_("This draft has no posting request yet."))
        conn, error = self._conn_for(MANAGER_ROLE)
        if error:
            self.write({"state": "failed", "last_error": error})
            raise UserError(error)
        try:
            # The rpc helper maps *args to the record ids and **kwargs to the
            # keyword arguments, so over_limit has to be a keyword here.
            rpc(conn, APPROVAL_MODEL, "action_approve", [self.approval_id],
                over_limit=bool(self.over_limit))
        except Exception as exc:
            message = rpc_error(exc)
            self.write({"last_error": message, "state": "failed"})
            raise UserError(message)
        self.write({
            "state": "approved",
            "approved_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    def action_refuse(self):
        """Refuse the posting request; the draft stays a draft."""
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("Only a waiting request can be refused."))
        conn, error = self._conn_for(MANAGER_ROLE)
        if error:
            self.write({"state": "failed", "last_error": error})
            raise UserError(error)
        try:
            if self.approval_id:
                rpc(conn, APPROVAL_MODEL, "action_reject", [self.approval_id])
        except Exception as exc:
            message = rpc_error(exc)
            self.write({"last_error": message})
            raise UserError(message)
        self.write({
            "state": "refused",
            "approved_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    def action_post(self):
        """Have the posting agent post the approved draft.

        The guard in the client database refuses the post when no approved
        request exists or when the amount is above the posting role's
        auto-post ceiling without an explicit over-limit authorisation.
        """
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only an approved request can be posted."))
        conn, error = self._conn_for(POSTING_ROLE)
        if error:
            self.write({"state": "failed", "last_error": error})
            raise UserError(error)
        try:
            rpc(conn, DRAFT_MODEL, "action_post", [self.move_id])
        except Exception as exc:
            message = rpc_error(exc)
            self.write({"last_error": message})
            raise UserError(message)
        self.write({
            "state": "posted",
            "posted_at": fields.Datetime.now(),
            "last_error": False,
        })
        return True

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_request_approvals(self):
        """Open a posting request for every draft a booking created."""
        Upload = self.env["sgc.accounting.upload"]
        # Only recent bookings: an old upload whose request was refused stays
        # refused and must not be reopened on every run.
        since = fields.Datetime.now() - timedelta(days=7)
        uploads = Upload.search(
            [("booking_state", "=", "done"), ("create_date", ">=", since)],
            order="id", limit=50,
        )
        opened = 0
        for upload in uploads:
            entries = upload.log_ids.filtered(
                lambda log: log.record_model == DRAFT_MODEL and log.record_id
            )
            for entry in entries:
                existing = self.search(
                    [
                        ("upload_id", "=", upload.id),
                        ("move_id", "=", entry.record_id),
                        ("state", "not in", ("refused",)),
                    ],
                    limit=1,
                )
                if existing:
                    continue
                request = self.create({
                    "client_id": upload.client_id.id,
                    "upload_id": upload.id,
                    "move_id": entry.record_id,
                    "move_name": entry.reference
                    or _("Draft %(id)s", id=entry.record_id),
                    "state": "pending",
                })
                if request._open_approval():
                    opened += 1
        if opened:
            _logger.info("Opened %s posting request(s).", opened)
        return True
