# -*- coding: utf-8 -*-
import uuid

from odoo import fields, models


class SgcAccountingProvisionEvent(models.Model):
    _name = "sgc.accounting.provision.event"
    _description = "Accounting Provisioning Event"
    _order = "create_date desc, id desc"

    event_id = fields.Char(
        required=True,
        default=lambda self: str(uuid.uuid4()),
        copy=False,
        index=True,
    )
    client_id = fields.Many2one(
        "sgc.accounting.client",
        string="Accounting Client",
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_type = fields.Selection(
        [
            ("provision", "Provision"),
            ("sync_companies", "Sync companies"),
            ("suspend", "Suspend"),
            ("resume", "Resume"),
            ("archive", "Archive"),
            ("delete", "Delete"),
        ],
        required=True,
    )
    payload = fields.Json()
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("rejected", "Rejected"),
            ("dead", "Dead"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    attempts = fields.Integer(default=0)
    next_attempt_at = fields.Datetime(default=fields.Datetime.now)
    last_status_code = fields.Integer()
    last_error = fields.Text()
    sent_at = fields.Datetime()

    _event_id_uniq = models.Constraint(
        "unique(event_id)",
        "A provisioning event with this id already exists.",
    )

    def action_retry(self):
        self.write(
            {
                "state": "pending",
                "next_attempt_at": fields.Datetime.now(),
                "last_error": False,
            }
        )
