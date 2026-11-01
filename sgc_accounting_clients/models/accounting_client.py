# -*- coding: utf-8 -*-
import logging
import os
import re
import xmlrpc.client
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Key files of the client databases live here, one per client
# (acc-<client_code>.env, written by scripts/link_accounting_client.sh).
# Never in the DB or git.
SECRETS_DIR = "/mnt/extra-addons/.secrets"
KEY_FILE_FIELDS = (
    "SGC_AGENT_API_KEY",
    "SGC_AGENT_ROLE",
    "SGC_AGENT_DB",
    "SGC_AGENT_USER_ID",
    "SGC_AGENT_ODOO_URL",
    "SGC_AGENT_KEY_EXPIRES",
)
INTAKE_ROLE = "agent-01-intake"
KEY_WARN_DAYS = 14
RPC_TIMEOUT = 30


# One summary for the link to-do, so it is found again to update or close.
LINK_TODO = "Accounting link needs attention"


class _Transport(xmlrpc.client.SafeTransport):
    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = RPC_TIMEOUT
        return connection


def rpc(conn, model, method, *args, **kwargs):
    """Call the client database over XML-RPC (https only) with its API key."""
    proxy = xmlrpc.client.ServerProxy(
        "%s/xmlrpc/2/object" % conn["url"], transport=_Transport(), allow_none=True
    )
    return proxy.execute_kw(
        conn["db"], conn["uid"], conn["key"], model, method, list(args), kwargs
    )


def rpc_error(exc):
    """Last line of a remote fault (the traceback above it is noise)."""
    text = (getattr(exc, "faultString", None) or str(exc) or repr(exc)).strip()
    return text.splitlines()[-1][:500] if text else repr(exc)

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
    api_user_id = fields.Integer(
        string="API User ID",
        help="res.users id of the intake API user inside the client database. "
        "Its API key goes in /mnt/extra-addons/.secrets/acc-<client code>.env "
        "as the line SGC_AGENT_API_KEY=<key>, never in the database.",
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
    agent_endpoint = fields.Char(
        help="Document-intake webhook for this client. Leave blank to use the "
        "global sgc_accounting_clients.agent_endpoint system parameter."
    )
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

    def _booking_connection(self):
        """Return ``(connection, error)`` for the client database.

        ``error`` says what staff still have to link; drafts wait until then.
        """
        self.ensure_one()
        missing = [
            label
            for label, value in (
                (_("Workspace URL"), self.workspace_url),
                (_("Database"), self.db_name),
                (_("API User ID"), self.api_user_id),
            )
            if not value
        ]
        if missing:
            return None, _(
                "The client database is not linked yet (missing: %(fields)s).",
                fields=", ".join(missing),
            )
        if not self.workspace_url.startswith("https://"):
            return None, _("The workspace URL must use https.")
        # The key file is bound to the client code (validated: [a-z0-9-]), so
        # one client's settings can never send another client's key.
        path = os.path.join(SECRETS_DIR, "acc-%s.env" % self.client_code)
        try:
            with open(path, encoding="utf-8") as handle:
                lines = dict(
                    line.strip().split("=", 1) for line in handle if "=" in line
                )
        except (OSError, ValueError) as exc:  # ValueError: not UTF-8
            return None, _(
                "The API key file cannot be read: %(error)s",
                error=getattr(exc, "strerror", None) or exc,
            )
        # The link script writes who the key belongs to; a key of another
        # database, user or role is refused before it is ever sent.
        missing = [name for name in KEY_FILE_FIELDS if not lines.get(name)]
        if missing:
            return None, _(
                "The API key file lacks %(fields)s; write it with "
                "scripts/link_accounting_client.sh.",
                fields=", ".join(missing),
            )
        if lines["SGC_AGENT_ROLE"] != INTAKE_ROLE:
            return None, _(
                "The API key belongs to role %(role)s; only %(intake)s may book.",
                role=lines["SGC_AGENT_ROLE"],
                intake=INTAKE_ROLE,
            )
        mismatch = [
            label
            for label, expected, found in (
                (_("database"), self.db_name, lines["SGC_AGENT_DB"]),
                (_("user"), str(self.api_user_id), lines["SGC_AGENT_USER_ID"]),
                (_("URL"), self.workspace_url, lines["SGC_AGENT_ODOO_URL"].rstrip("/")),
            )
            if expected != found
        ]
        if mismatch:
            return None, _(
                "The API key file is for another %(what)s than the one linked "
                "on this client.",
                what=", ".join(mismatch),
            )
        try:
            expires = fields.Datetime.to_datetime(
                lines["SGC_AGENT_KEY_EXPIRES"][:19].replace("T", " ")
            )
        except ValueError:
            return None, _("The API key file has an unreadable expiry date.")
        if expires <= fields.Datetime.now():
            return None, _(
                "The API key expired on %(date)s; rotate it with "
                "scripts/link_accounting_client.sh.",
                date=expires.date(),
            )
        return {
            "url": self.workspace_url,
            "db": self.db_name,
            "uid": self.api_user_id,
            "key": lines["SGC_AGENT_API_KEY"],
            "expires": expires,
        }, None

    def _verify_remote(self, conn, company_ids):
        """Refuse unless the API user is the draft-only intake agent of the
        given companies, so a misconfigured key can never post.

        Returns the companies the agent may book into, as ``{id: name}``.
        """
        try:
            remote_user = rpc(
                conn,
                "res.users",
                "read",
                [conn["uid"]],
                fields=["company_ids", "sgc_agent_role_id"],
            )
        except xmlrpc.client.Fault as exc:
            if "sgc_agent_role_id" in (exc.faultString or ""):
                raise UserError(
                    _(
                        "The module sgc_accounting_agents is not installed in "
                        "%(db)s, so nothing stops the API user from posting.",
                        db=conn["db"],
                    )
                ) from exc
            raise
        role_id = remote_user and remote_user[0]["sgc_agent_role_id"]
        role = (
            rpc(conn, "sgc.agent.role", "read", [role_id[0]], fields=["code", "company_ids"])
            if role_id
            else []
        )
        if not role or role[0]["code"] != INTAKE_ROLE:
            raise UserError(
                _(
                    "API user %(uid)s in %(db)s is not the %(intake)s agent; "
                    "it might be able to post.",
                    uid=conn["uid"],
                    db=conn["db"],
                    intake=INTAKE_ROLE,
                )
            )
        allowed = set(remote_user[0]["company_ids"])
        if role[0]["company_ids"]:
            allowed &= set(role[0]["company_ids"])
        missing = sorted(set(company_ids) - allowed)
        if missing:
            raise UserError(
                _(
                    "The intake agent of %(db)s may not work on company id(s) "
                    "%(ids)s; re-run scripts/link_accounting_client.sh with them.",
                    db=conn["db"],
                    ids=", ".join(map(str, missing)),
                )
            )
        companies = rpc(
            conn, "res.company", "search_read", [("id", "in", sorted(allowed))],
            fields=["id", "name"],
        )
        return {company["id"]: company["name"] for company in companies}

    def _check_connection(self):
        """Verify the link end to end and record the outcome on the client.

        Returns ``(companies, error)``; a failure or a key expiring within
        KEY_WARN_DAYS also gives the account manager a to-do.
        """
        self.ensure_one()
        conn, error = self._booking_connection()
        companies = {}
        if not error:
            mapped = self.company_ids.filtered("active").mapped("odoo_company_id")
            try:
                companies = self._verify_remote(conn, mapped)
            except Exception as exc:
                error = _(
                    "Connection to %(db)s failed: %(error)s",
                    db=conn["db"],
                    error=rpc_error(exc),
                )
        self.write({"last_health_check": fields.Datetime.now(), "last_error": error or False})
        warning = error
        if not error and conn["expires"] - fields.Datetime.now() < timedelta(
            days=KEY_WARN_DAYS
        ):
            warning = _(
                "The API key of %(db)s expires on %(date)s; rotate it with "
                "scripts/link_accounting_client.sh.",
                db=conn["db"],
                date=conn["expires"].date(),
            )
        summary = LINK_TODO
        if warning:
            self._todo(summary, warning)
        else:
            # Healthy again: close the stale alarm so the next one is noticed.
            self.activity_ids.filtered(
                lambda activity: activity.summary == summary
            ).action_feedback(feedback=_("The link is healthy again."))
        return companies, error

    @api.model
    def _cron_check_connections(self):
        # Least recently checked first, committed per client: a run cut short
        # by unreachable databases keeps its results and the next one goes on.
        for client in self.search(
            [("db_name", "!=", False), ("api_user_id", "!=", 0)],
            order="last_health_check asc nulls first, id",
        ):
            try:
                with self.env.cr.savepoint():
                    client._check_connection()
            except Exception as exc:
                # One broken client must not stop (or, never being marked
                # checked, forever head) the run.
                _logger.exception("Link check failed for client %s", client.id)
                client.write({"last_health_check": fields.Datetime.now(), "last_error": str(exc)})
            if self.env.context.get("ir_cron_progress_id"):
                self.env["ir.cron"]._commit_progress(1)
        return True

    def action_test_connection(self):
        self.ensure_one()
        companies, error = self._check_connection()
        if error:
            # A notification, not an exception: raising would roll back the
            # recorded error and the to-do.
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection to %(db)s failed", db=self.db_name),
                    "message": error,
                    "type": "danger",
                    "sticky": True,
                },
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Connected to %(db)s", db=self.db_name),
                "message": _(
                    "The intake agent may book into (id name): %(list)s",
                    list=", ".join(
                        "%s %s" % (company_id, name)
                        for company_id, name in sorted(companies.items())
                    ),
                ),
                "type": "success",
                "sticky": True,
            },
        }

    def _reviewer(self):
        """The account manager, else the first agency manager.

        A client created by the checkout gets OdooBot as account manager,
        which no one reads.
        """
        self.ensure_one()

        def usable(user):
            return user.active and not user.share and not user._is_superuser()

        if self.account_manager_id and usable(self.account_manager_id):
            return self.account_manager_id
        group = self.env.ref(
            "sgc_accounting_clients.group_sgc_accounting_manager",
            raise_if_not_found=False,
        )
        return (group.all_user_ids.filtered(usable) if group else self.env["res.users"])[:1]

    def _todo(self, summary, note, record=None):
        """One open to-do per record and summary for the reviewer."""
        self.ensure_one()
        record = record or self
        reviewer = self._reviewer()
        if not reviewer:
            _logger.warning("No reviewer for %s: %s", record, note)
            return
        existing = record.activity_ids.filtered(
            lambda activity: activity.summary == summary
        )
        if existing:
            existing.note = note  # the current reason, not the first one
            return
        record.activity_schedule(
            "mail.mail_activity_data_todo", user_id=reviewer.id, summary=summary, note=note
        )

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
