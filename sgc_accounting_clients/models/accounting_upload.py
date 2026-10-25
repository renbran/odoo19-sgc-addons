# -*- coding: utf-8 -*-
import base64
import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .accounting_bucket import DOC_TYPES

STATE_SELECTION = [
    ("received", "Received"),
    ("validated", "Validated"),
    ("processing", "Processing"),
    ("processed", "Processed"),
    ("quarantined", "Quarantined"),
    ("failed", "Failed"),
]


class SgcAccountingUpload(models.Model):
    _name = "sgc.accounting.upload"
    _description = "Accounting Document Upload"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    client_id = fields.Many2one(
        "sgc.accounting.client",
        string="Accounting Client",
        required=True,
        ondelete="cascade",
        index=True,
    )
    accounting_company_id = fields.Many2one(
        "sgc.accounting.company",
        string="Company",
        domain="[('client_id', '=', client_id)]",
        ondelete="set null",
    )
    doc_type = fields.Selection(
        DOC_TYPES, string="Document Type", required=True, tracking=True
    )
    filename = fields.Char(required=True)
    mimetype = fields.Char(string="MIME Type")
    file = fields.Binary(required=True, attachment=True)
    file_size = fields.Integer(compute="_compute_file_meta", store=True)
    file_size_human = fields.Char(compute="_compute_file_meta", store=True)
    sha256 = fields.Char(compute="_compute_file_meta", store=True, index=True)
    storage_path = fields.Char(compute="_compute_storage_path", store=True)
    state = fields.Selection(
        STATE_SELECTION,
        default="received",
        required=True,
        tracking=True,
        index=True,
    )
    doc_type_label = fields.Char(compute="_compute_labels")
    state_label = fields.Char(compute="_compute_labels")
    validation_errors = fields.Text()
    agent_run_id = fields.Char(
        string="Agent Run ID", help="UUID of the latest queued agent run."
    )
    agent_run_ids = fields.One2many(
        "sgc.accounting.agent.run",
        "upload_id",
        string="Agent Runs",
        readonly=True,
    )
    agent_state = fields.Selection(
        [
            ("queued", "Queued"),
            ("dispatched", "Dispatched"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
        ],
        string="Agent Status",
        compute="_compute_agent_state",
        store=True,
    )
    agent_state_label = fields.Char(compute="_compute_agent_state", store=True)
    row_count = fields.Integer(string="Data Rows", readonly=True)
    format_headers = fields.Text(string="Detected Headers", readonly=True)
    odoo_move_ids = fields.Text(string="Odoo Move IDs")
    uploaded_by_id = fields.Many2one(
        "res.partner",
        string="Uploaded By",
        default=lambda self: self.env.user.partner_id,
        ondelete="set null",
    )
    processed_at = fields.Datetime()
    notes = fields.Text()

    @api.depends("doc_type", "filename")
    def _compute_name(self):
        labels = dict(DOC_TYPES)
        for upload in self:
            upload.name = "%s - %s" % (
                labels.get(upload.doc_type, _("Document")),
                upload.filename or _("Untitled"),
            )

    @api.depends("file")
    def _compute_file_meta(self):
        for upload in self:
            raw = base64.b64decode(upload.file) if upload.file else b""
            upload.file_size = len(raw)
            upload.file_size_human = self._human_size(len(raw))
            upload.sha256 = hashlib.sha256(raw).hexdigest() if raw else False

    @api.depends(
        "client_id.client_code",
        "client_id.storage_root",
        "doc_type",
        "filename",
        "sha256",
    )
    def _compute_storage_path(self):
        for upload in self:
            if not upload.client_id or not upload.sha256:
                upload.storage_path = False
                continue
            root = (
                upload.client_id.storage_root
                or "/srv/sgc/accounting/clients"
            ).rstrip("/")
            code = upload.client_id.client_code or "client"
            doc_type = upload.doc_type or "other"
            stamp = fields.Datetime.now().strftime("%Y/%m")
            upload.storage_path = "%s/%s/inbox/%s/%s/%s_%s" % (
                root,
                code,
                doc_type,
                stamp,
                upload.sha256[:12],
                upload.filename or "document",
            )

    @api.depends("doc_type", "state")
    def _compute_labels(self):
        doc_labels = dict(DOC_TYPES)
        state_labels = dict(STATE_SELECTION)
        for upload in self:
            upload.doc_type_label = doc_labels.get(upload.doc_type, "")
            upload.state_label = state_labels.get(upload.state, "")

    @api.depends("agent_run_ids.state", "agent_run_ids.create_date")
    def _compute_agent_state(self):
        labels = dict(self._fields["agent_state"].selection)
        for upload in self:
            run = upload.agent_run_ids.sorted(
                key=lambda item: (item.create_date or fields.Datetime.now(), item.id),
                reverse=True,
            )[:1]
            upload.agent_state = run.state if run else False
            upload.agent_state_label = labels.get(run.state, "") if run else _("Not queued")

    @staticmethod
    def _human_size(size):
        value = float(size or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024.0 or unit == "GB":
                return "%.1f %s" % (value, unit)
            value /= 1024.0
        return "%d B" % (size or 0)

    @api.constrains("client_id", "accounting_company_id")
    def _check_company_client(self):
        for upload in self:
            if upload.accounting_company_id and upload.accounting_company_id.client_id != upload.client_id:
                raise ValidationError(
                    _("The selected company does not belong to this client.")
                )

    @api.constrains("file_size")
    def _check_file_size(self):
        limit = 50 * 1024 * 1024
        for upload in self:
            if upload.file_size and upload.file_size > limit:
                raise ValidationError(
                    _("The uploaded file is larger than the 50 MB limit.")
                )

    def action_mark_validated(self):
        self.write({"state": "validated", "validation_errors": False})

    def action_quarantine(self):
        self.write({"state": "quarantined"})

    def action_reset(self):
        self.write({"state": "received"})

    def action_queue_agent(self):
        """Mark an accepted upload as validated and create one agent run.

        The agent is an external service.  This method only creates the durable
        outbox record; the cron dispatcher performs the HTTP call.  This keeps
        the customer upload fast and prevents a failed agent from losing the
        document.
        """
        runs = self.env["sgc.accounting.agent.run"]
        for upload in self:
            if upload.state not in ("received", "validated"):
                continue
            existing = upload.agent_run_ids.filtered(
                lambda run: run.state in ("queued", "dispatched", "running", "completed")
            )
            if existing:
                continue
            upload.write({"state": "validated"})
            run = runs.create({"upload_id": upload.id})
            upload.write({"agent_run_id": run.run_id})
        return True
