# -*- coding: utf-8 -*-
"""Provisioning outbox processor.

Consumes ``sgc.accounting.provision.event`` records in ``pending`` state and
dispatches them to the accounting tenant receiver endpoint.  The receiver is
expected to create the client database, agent service users and API keys, then
call back with the connection details so the client workspace can be activated.

This closes the gap where provisioning events were written to the outbox but
no automated consumer existed — every new client required manual shell scripts.
"""
import json
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_PROVISION_ATTEMPTS = 5
PROVISION_TIMEOUT = 30


class SgcAccountingProvisionEvent(models.Model):
    _inherit = "sgc.accounting.provision.event"

    receiver_endpoint = fields.Char(
        readonly=True,
        help="Endpoint the event was sent to.",
    )
    receiver_response = fields.Text(readonly=True)

    def _receiver_endpoint(self):
        """Resolve the tenant receiver URL from system parameters or client."""
        param = self.env["ir.config_parameter"].sudo()
        endpoint = param.get_param("sgc_accounting_clients.provision_endpoint")
        if not endpoint:
            # Fall back to the agent endpoint (the orchestrator may handle both).
            endpoint = param.get_param("sgc_accounting_clients.agent_endpoint")
        return (endpoint or "").strip()

    def _receiver_token(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sgc_accounting_clients.provision_token", "")
            .strip()
        )

    def _send_to_receiver(self):
        """Send this event to the tenant receiver and update its state."""
        self.ensure_one()
        endpoint = self._receiver_endpoint()
        if not endpoint:
            self.write({
                "last_error": _("No provision endpoint is configured."),
                "next_attempt_at": fields.Datetime.now() + timedelta(hours=1),
            })
            return False
        payload = self.payload or {}
        payload["event_id"] = self.event_id
        payload["event_type"] = self.event_type
        try:
            import requests
        except ImportError:
            self.write({
                "last_error": "The requests library is not available.",
                "next_attempt_at": fields.Datetime.now() + timedelta(hours=1),
            })
            return False
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-SGC-Event": "accounting.provision.%s" % self.event_type,
            "X-SGC-Event-Id": self.event_id,
        }
        token = self._receiver_token()
        if token:
            headers["Authorization"] = "Bearer %s" % token
        try:
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=PROVISION_TIMEOUT,
            )
        except Exception as exc:
            self._record_provision_failure(str(exc)[:2000])
            return False
        body = (response.text or "")[:4000]
        if response.status_code < 200 or response.status_code >= 300:
            self._record_provision_failure(
                "HTTP %s: %s" % (response.status_code, body[:500])
            )
            return False
        # The receiver may return connection details inline.
        connection = {}
        try:
            data = response.json()
            if isinstance(data, dict):
                connection = data.get("connection", {})
        except (ValueError, TypeError):
            pass
        self.write({
            "state": "sent",
            "sent_at": fields.Datetime.now(),
            "attempts": (self.attempts or 0) + 1,
            "last_status_code": response.status_code,
            "last_error": False,
            "receiver_endpoint": endpoint,
            "receiver_response": body,
        })
        # Apply the returned connection details to the client.
        if connection and self.event_type == "provision":
            self._apply_connection(connection)
        return True

    def _record_provision_failure(self, message):
        attempts = (self.attempts or 0) + 1
        self.write({
            "attempts": attempts,
            "state": "dead" if attempts >= MAX_PROVISION_ATTEMPTS else "pending",
            "last_error": message,
            "next_attempt_at": fields.Datetime.now()
            + timedelta(minutes=min(2 ** attempts, 60)),
        })

    def _apply_connection(self, connection):
        """Apply the connection details returned by the receiver to the client.

        The receiver creates the database, agent users and API keys, and returns
        just enough to wire the workspace: the database name, workspace URL,
        API user id and the path to the key file (written by the receiver on the
        shared secrets volume).
        """
        self.ensure_one()
        client = self.client_id
        vals = {}
        if connection.get("db_name") and not client.db_name:
            vals["db_name"] = connection["db_name"]
        if connection.get("workspace_url") and not client.workspace_url:
            vals["base_url"] = connection["workspace_url"].rstrip("/")
        if connection.get("api_user_id") and not client.api_user_id:
            vals["api_user_id"] = connection["api_user_id"]
        if vals:
            client.sudo().write(vals)
            client.message_post(body=_(
                "Provisioning receiver returned connection details: "
                "database %(db)s, workspace %(url)s.",
                db=vals.get("db_name", "-"),
                url=vals.get("base_url", "-"),
            ))
        # Mark the client as active once provisioned.
        if client.status in ("queued", "provisioning", "failed"):
            client.sudo().write({
                "status": "active",
                "provisioned_at": fields.Datetime.now(),
                "last_error": False,
            })
            client.message_post(body=_(
                "Workspace is now active and ready for document uploads."
            ))

    @api.model
    def _cron_process_provision_events(self):
        """Process pending provisioning events (every 5 minutes)."""
        events = self.search(
            [
                ("state", "=", "pending"),
                ("next_attempt_at", "<=", fields.Datetime.now()),
            ],
            limit=20,
            order="next_attempt_at, id",
        )
        for event in events:
            # Suspend/archive/delete events need the client to exist first.
            if event.event_type == "provision":
                event.client_id.sudo().write({"status": "provisioning"})
            try:
                event._send_to_receiver()
            except Exception:
                _logger.exception(
                    "Provision event %s failed", event.event_id
                )
        # Mark dead events to the account manager. The to-do hangs on the
        # CLIENT, not on the event: sgc.accounting.provision.event does not
        # inherit mail.thread, so it has no activity_ids to write on.
        dead = self.search([("state", "=", "dead"), ("last_error", "!=", False)])
        for event in dead:
            event.client_id._todo(
                "Provisioning failed",
                _(
                    "Provisioning event %(event)s for %(client)s failed after "
                    "%(n)s attempts: %(error)s",
                    event=event.event_id,
                    client=event.client_id.name,
                    n=event.attempts,
                    error=event.last_error,
                ),
            )
        return True
