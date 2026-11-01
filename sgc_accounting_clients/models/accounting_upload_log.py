# -*- coding: utf-8 -*-
from odoo import fields, models

LOG_EVENTS = [
    ("uploaded", "Uploaded"),
    ("booked", "Draft created"),
    ("duplicate", "Duplicate blocked"),
    ("waiting", "Waiting for database"),
    ("skipped", "Not booked"),
    ("failed", "Failed"),
    ("agent_result", "Agent result"),
]


class SgcAccountingUploadLog(models.Model):
    """Append-only backend log of what happened to an uploaded file.

    It records which client database and company the file was booked into,
    so the agent and the accountant see the same target the upload had.
    """

    _name = "sgc.accounting.upload.log"
    _description = "Accounting Upload Log"
    _order = "id desc"

    upload_id = fields.Many2one(
        "sgc.accounting.upload",
        string="Document",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    client_id = fields.Many2one(
        related="upload_id.client_id", store=True, index=True
    )
    event = fields.Selection(LOG_EVENTS, required=True, readonly=True, index=True)
    target_db = fields.Char(string="Target Database", readonly=True)
    target_company_ref = fields.Integer(string="Target Company ID", readonly=True)
    record_model = fields.Char(string="Record Model", readonly=True)
    record_id = fields.Integer(string="Record ID", readonly=True)
    reference = fields.Char(readonly=True)
    message = fields.Text(readonly=True)
