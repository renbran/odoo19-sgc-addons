# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

RESERVED_CODES = {
    "www",
    "app",
    "admin",
    "api",
    "mail",
    "books",
    "demo",
    "staging",
    "test",
    "upload",
    "download",
}

CLIENT_STATUSES = [
    ("draft", "Draft"),
    ("ready", "Ready"),
    ("queued", "Queued"),
    ("provisioning", "Provisioning"),
    ("active", "Active"),
    ("suspended", "Suspended"),
    ("failed", "Failed"),
    ("archived", "Archived"),
]


class SgcAccountingClient(models.Model):
    _name = "sgc.accounting.client"
    _description = "Accounting Client Workspace"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _rec_name = "name"

    name = fields.Char(required=True, tracking=True)
    client_code = fields.Char(
        required=True,
        copy=False,
        tracking=True,
        help="Stable workspace code used in URLs and database names.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )
    legal_name = fields.Char()
    trn = fields.Char(string="TRN", size=15, tracking=True)
    trade_license_no = fields.Char(string="Trade Licence No.")
    emirate = fields.Char()
    fiscal_year_end = fields.Char(string="Fiscal Year End", default="12-31")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )
    vat_registered = fields.Boolean(default=True)
    corporate_tax_registered = fields.Boolean(default=True)
    status = fields.Selection(
        CLIENT_STATUSES,
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    status_label = fields.Char(compute="_compute_status_label")
    active = fields.Boolean(default=True)

    db_name = fields.Char(string="Database", copy=False)
    db_host = fields.Char(string="Database Host", default="accounting-db")
    db_port = fields.Integer(string="Database Port", default=5432)
    db_user = fields.Char(string="Database User", default="odoo")
    db_secret_ref = fields.Char(
        string="Database Secret Reference",
        help="Reference to the password in the receiver secret store, never the password itself.",
    )
    base_url = fields.Char(
        string="Workspace URL",
        help="Public URL of the client workspace, for example https://demo.sgctech.ai.",
    )
    workspace_url = fields.Char(compute="_compute_workspace_url", store=True)
    mcp_url = fields.Char(string="MCP URL")

    storage_backend = fields.Selection(
        [("local", "Local ext4"), ("s3", "S3 / Cloudflare R2")],
        default="local",
        required=True,
    )
    storage_bucket = fields.Char()
    storage_root = fields.Char(default="/srv/sgc/accounting/clients")
    inbox_paths = fields.Text(
        help="One inbox path per document type. Leave empty to use the computed layout."
    )
    processed_path = fields.Char()
    quarantine_path = fields.Char()
    archive_path = fields.Char()

    assigned_agent = fields.Char(default="agent-00")
    account_manager_id = fields.Many2one(
        "res.users",
        string="Account Manager",
        default=lambda self: self.env.user,
        tracking=True,
    )
    hitl_reviewer_email = fields.Char(
        string="HITL Reviewer Email",
        help="Email of the human reviewer inside the client database. Odoo user ids are per database.",
    )
    auto_post_max_aed = fields.Float(string="Auto-post Max (AED)", default=10000.0)
    min_confidence = fields.Float(string="Minimum Confidence", default=0.90)
    require_trn = fields.Boolean(string="Require 15-digit TRN", default=True)
    retention_policy = fields.Char(
        default="UAE VAT 5 years / Corporate Tax 7 years"
    )
    retention_until = fields.Date()
    data_residency = fields.Char(default="UAE")
    provisioned_at = fields.Datetime()
    last_health_check = fields.Datetime()
    last_error = fields.Text()

    company_ids = fields.One2many(
        "sgc.accounting.company", "client_id", string="Companies"
    )
    default_company_id = fields.Many2one(
        "sgc.accounting.company",
        string="Default Company",
        domain="[('client_id', '=', id)]",
    )
    upload_ids = fields.One2many(
        "sgc.accounting.upload", "client_id", string="Documents"
    )
    company_count = fields.Integer(compute="_compute_counts")
    upload_count = fields.Integer(compute="_compute_counts")
    pending_upload_count = fields.Integer(compute="_compute_counts")
    notes = fields.Html()

    _client_code_uniq = models.Constraint(
        "unique(client_code)",
        "An accounting workspace already uses this client code.",
    )

    @api.depends("base_url")
    def _compute_workspace_url(self):
        for client in self:
            client.workspace_url = (client.base_url or "").rstrip("/") or False

    @api.depends("status")
    def _compute_status_label(self):
        labels = dict(self._fields["status"].selection)
        for client in self:
            client.status_label = labels.get(client.status, "")

    @api.depends("company_ids", "upload_ids.state")
    def _compute_counts(self):
        for client in self:
            client.company_count = len(client.company_ids)
            client.upload_count = len(client.upload_ids)
            client.pending_upload_count = len(
                client.upload_ids.filtered(
                    lambda upload: upload.state
                    in ("received", "validated", "processing")
                )
            )

    @api.constrains("client_code")
    def _check_client_code(self):
        for client in self:
            code = (client.client_code or "").strip().lower()
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?", code):
                raise ValidationError(
                    _(
                        "Client code must be 2-32 characters, lowercase letters, "
                        "digits or hyphens, and cannot start or end with a hyphen."
                    )
                )
            if code in RESERVED_CODES:
                raise ValidationError(
                    _("The client code %(code)s is reserved.", code=code)
                )

    @api.constrains("trn")
    def _check_trn(self):
        for client in self:
            if client.trn and (
                len(client.trn) != 15 or not client.trn.isdigit()
            ):
                raise ValidationError(
                    _("A UAE TRN must contain exactly 15 digits.")
                )

    def _provision_payload(self):
        self.ensure_one()
        return {
            "client_code": self.client_code,
            "db_name": self.db_name,
            "partner_id": self.partner_id.id,
            "partner_name": self.partner_id.name,
            "legal_name": self.legal_name or self.name,
            "trn": self.trn or "",
            "workspace_url": self.workspace_url or "",
            "storage_root": self.storage_root or "",
            "companies": [
                {
                    "odoo_company_id": company.odoo_company_id,
                    "name": company.name,
                    "trn": company.trn or "",
                    "is_default": company.is_default,
                    "currency": company.currency_id.name or "",
                }
                for company in self.company_ids
            ],
            "requested_by": self.env.user.id,
            "requested_at": fields.Datetime.now().isoformat(),
        }

    def action_queue_provision(self):
        self.ensure_one()
        if not self.client_code:
            raise UserError(_("Set a client code before provisioning."))
        event = self.env["sgc.accounting.provision.event"].create(
            {
                "client_id": self.id,
                "event_type": "provision",
                "payload": self._provision_payload(),
            }
        )
        self.write({"status": "queued", "last_error": False})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Provisioning queued"),
                "message": _("Event %(event)s is ready for the accounting receiver.", event=event.event_id),
                "type": "success",
                "sticky": False,
            },
        }

    def action_sync_companies(self):
        self.ensure_one()
        event = self.env["sgc.accounting.provision.event"].create(
            {
                "client_id": self.id,
                "event_type": "sync_companies",
                "payload": self._provision_payload(),
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Company sync queued"),
                "message": _("Event %(event)s is ready for the accounting receiver.", event=event.event_id),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_workspace(self):
        self.ensure_one()
        if not self.workspace_url:
            raise UserError(_("Set the workspace URL first."))
        return {
            "type": "ir.actions.act_url",
            "url": self.workspace_url,
            "target": "new",
        }

    def action_open_uploads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents"),
            "res_model": "sgc.accounting.upload",
            "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }

    def action_open_companies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Companies"),
            "res_model": "sgc.accounting.company",
            "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }
