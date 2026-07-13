import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

LOCAL_PART_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")
BYTES_PER_MIB = 1024 * 1024


class MailcowMailbox(models.Model):
    _name = "mailcow.mailbox"
    _description = "Mailcow Mailbox"
    _inherit = ["mail.thread"]
    _order = "email"
    _rec_name = "email"

    # Identity -----------------------------------------------------------
    local_part = fields.Char(
        required=True, tracking=True,
        help="The part before the @. Lowercase letters, digits, dot, "
             "dash and underscore only.")
    domain = fields.Char(
        required=True, tracking=True,
        default=lambda self: self.env["ir.config_parameter"].sudo().get_param(
            "sgc_mailcow.default_domain"))
    email = fields.Char(
        compute="_compute_email", store=True, string="Email Address")
    name = fields.Char(
        string="Display Name", required=True,
        help="Full name shown on outgoing mail (e.g. the employee's name).")

    # Credentials --------------------------------------------------------
    password = fields.Char(
        copy=False,
        help="Initial mailbox password. Cleared from Odoo after the mailbox "
             "is created in Mailcow.")
    force_pw_update = fields.Boolean(
        string="Force Password Change", default=True,
        help="Require the employee to set a new password on first login.")

    # Mailbox settings ---------------------------------------------------
    quota_mb = fields.Integer(
        string="Quota (MB)", tracking=True,
        default=lambda self: int(self.env["ir.config_parameter"].sudo().get_param(
            "sgc_mailcow.default_quota_mb", "3072")))
    quota_used_mb = fields.Integer(string="Used (MB)", readonly=True)
    mailbox_active = fields.Boolean(
        string="Mailbox Enabled", default=True, tracking=True,
        help="Disabled mailboxes keep all their mail but reject login, "
             "IMAP and SMTP.")
    tls_enforce_in = fields.Boolean(string="Enforce TLS Incoming")
    tls_enforce_out = fields.Boolean(string="Enforce TLS Outgoing")
    tags = fields.Char(help="Comma-separated Mailcow tags, e.g. sales,dubai")

    # Links --------------------------------------------------------------
    employee_id = fields.Many2one(
        "hr.employee", string="Employee", ondelete="set null", tracking=True)
    user_id = fields.Many2one(
        "res.users", string="Odoo User", ondelete="set null",
        help="Optional link to the Odoo login of the mailbox owner.")

    # Provisioning -------------------------------------------------------
    provision_smtp = fields.Boolean(
        string="Create Outgoing SMTP Server", default=True,
        help="Create the matching 'SMTP - email' entry in Odoo outgoing "
             "mail servers when the mailbox is created.")
    provision_fetchmail = fields.Boolean(
        string="Create Incoming IMAP Server", default=False,
        help="Create a fetchmail (incoming) server for this mailbox.")
    smtp_server_id = fields.Many2one(
        "ir.mail_server", string="SMTP Server", readonly=True, copy=False)
    fetchmail_server_id = fields.Many2one(
        "fetchmail.server", string="IMAP Server", readonly=True, copy=False)

    # State --------------------------------------------------------------
    state = fields.Selection([
        ("draft", "Draft"),
        ("synced", "In Mailcow"),
        ("missing", "Missing in Mailcow"),
    ], default="draft", required=True, tracking=True, copy=False)
    last_sync = fields.Datetime(readonly=True, copy=False)

    _sql_constraints = [
        ("email_uniq", "unique (local_part, domain)",
         "A mailbox with this address already exists in Odoo."),
    ]

    # ------------------------------------------------------------------
    # Computes / constraints
    # ------------------------------------------------------------------
    @api.depends("local_part", "domain")
    def _compute_email(self):
        for rec in self:
            rec.email = (
                "%s@%s" % (rec.local_part, rec.domain)
                if rec.local_part and rec.domain else False)

    @api.constrains("local_part")
    def _check_local_part(self):
        for rec in self:
            if rec.local_part and not LOCAL_PART_RE.match(rec.local_part):
                raise ValidationError(_(
                    "Invalid local part '%s': use lowercase letters, digits, "
                    "dot, dash or underscore, starting and ending with a "
                    "letter or digit.", rec.local_part))

    @api.constrains("quota_mb")
    def _check_quota(self):
        for rec in self:
            if rec.quota_mb <= 0:
                raise ValidationError(_("Quota must be a positive number of MB."))

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id and not rec.name:
                rec.name = rec.employee_id.name
            if rec.employee_id and not rec.local_part and rec.employee_id.work_email:
                rec.local_part = rec.employee_id.work_email.split("@")[0].lower()
            if rec.employee_id and not rec.user_id:
                rec.user_id = rec.employee_id.user_id

    # ------------------------------------------------------------------
    # Mailcow actions
    # ------------------------------------------------------------------
    def action_create_in_mailcow(self):
        api_client = self.env["mailcow.api"]
        for rec in self:
            if rec.state == "synced":
                raise UserError(_("%s already exists in Mailcow.", rec.email))
            if not rec.password:
                raise UserError(_(
                    "Set an initial password for %s before creating the "
                    "mailbox.", rec.email))
            api_client.add_mailbox({
                "local_part": rec.local_part,
                "domain": rec.domain,
                "name": rec.name,
                "password": rec.password,
                "quota": rec.quota_mb,
                "active": rec.mailbox_active,
                "force_pw_update": rec.force_pw_update,
                "tls_enforce_in": rec.tls_enforce_in,
                "tls_enforce_out": rec.tls_enforce_out,
                "tags": [t.strip() for t in rec.tags.split(",")] if rec.tags else None,
            })
            rec._provision_odoo_servers()
            rec.write({
                "state": "synced",
                "last_sync": fields.Datetime.now(),
                # Don't keep the initial password in the Odoo DB once it
                # has served its purpose.
                "password": False,
            })
            rec.message_post(body=_("Mailbox created in Mailcow."))
        return True

    def action_disable_mailbox(self):
        self._set_active_in_mailcow(False)
        return True

    def action_enable_mailbox(self):
        self._set_active_in_mailcow(True)
        return True

    def _set_active_in_mailcow(self, active):
        api_client = self.env["mailcow.api"]
        for rec in self:
            if rec.state != "synced":
                raise UserError(_(
                    "%s is not in Mailcow yet — create it first.", rec.email))
            api_client.set_mailbox_active(rec.email, active)
            rec.write({
                "mailbox_active": active,
                "last_sync": fields.Datetime.now(),
            })
            # Keep the Odoo-side servers in step so a disabled employee
            # cannot keep sending through Odoo.
            if rec.smtp_server_id:
                rec.smtp_server_id.active = active
            if rec.fetchmail_server_id:
                rec.fetchmail_server_id.active = active
            rec.message_post(body=_(
                "Mailbox %s in Mailcow.", _("enabled") if active else _("disabled")))

    def action_push_settings(self):
        """Push name / quota / TLS / tags changes to an existing mailbox."""
        api_client = self.env["mailcow.api"]
        for rec in self:
            if rec.state != "synced":
                raise UserError(_(
                    "%s is not in Mailcow yet — create it first.", rec.email))
            attr = {
                "name": rec.name,
                "quota": str(rec.quota_mb),
                "tls_enforce_in": "1" if rec.tls_enforce_in else "0",
                "tls_enforce_out": "1" if rec.tls_enforce_out else "0",
            }
            if rec.tags:
                attr["tags"] = [t.strip() for t in rec.tags.split(",")]
            api_client.edit_mailbox(rec.email, attr)
            rec.last_sync = fields.Datetime.now()
            rec.message_post(body=_("Mailbox settings pushed to Mailcow."))
        return True

    def action_sync_now(self):
        self._sync_from_mailcow()
        return True

    # ------------------------------------------------------------------
    # Odoo-side provisioning (mirrors the existing manual pattern)
    # ------------------------------------------------------------------
    def _provision_odoo_servers(self):
        self.ensure_one()
        host = self.env["mailcow.api"].get_mail_host()
        if self.provision_smtp and not self.smtp_server_id:
            self.smtp_server_id = self.env["ir.mail_server"].sudo().create({
                "name": "SMTP - %s" % self.email,
                "smtp_host": host,
                "smtp_port": 587,
                "smtp_encryption": "starttls",
                "smtp_user": self.email,
                "smtp_pass": self.password,
                "from_filter": self.email,
                "active": True,
            })
        if self.provision_fetchmail and not self.fetchmail_server_id:
            self.fetchmail_server_id = self.env["fetchmail.server"].sudo().create({
                "name": "Mailcow - %s" % self.email,
                "server_type": "imap",
                "server": host,
                "port": 993,
                "is_ssl": True,
                "user": self.email,
                "password": self.password,
                "active": True,
            })

    # ------------------------------------------------------------------
    # Polling sync (Mailcow has no webhooks)
    # ------------------------------------------------------------------
    @api.model
    def _cron_sync_mailboxes(self):
        if not self.env["mailcow.api"].is_configured():
            _logger.info("Mailcow sync skipped: connection not configured.")
            return
        try:
            self.search([])._sync_from_mailcow(create_unknown=True)
        except UserError as exc:
            # Never let a flaky mail server break the cron worker.
            _logger.warning("Mailcow sync failed: %s", exc)

    def _sync_from_mailcow(self, create_unknown=False):
        api_client = self.env["mailcow.api"]
        domain = self.env["ir.config_parameter"].sudo().get_param(
            "sgc_mailcow.default_domain")
        if not domain:
            raise UserError(_(
                "Set the default mail domain in Settings → Mailcow first."))
        remote = {
            mb.get("username"): mb
            for mb in api_client.get_mailboxes(domain)
            if mb.get("username")
        }
        now = fields.Datetime.now()
        known = self.search([("domain", "=", domain)]) | self
        for rec in known.filtered(lambda r: r.domain == domain):
            data = remote.pop(rec.email, None)
            if data is None:
                if rec.state == "synced":
                    rec.write({"state": "missing", "last_sync": now})
                continue
            rec.write({
                "state": "synced",
                "name": data.get("name") or rec.name,
                "mailbox_active": str(data.get("active", "1")) == "1",
                "quota_mb": int(data.get("quota") or 0) // BYTES_PER_MIB or rec.quota_mb,
                "quota_used_mb": int(data.get("quota_used") or 0) // BYTES_PER_MIB,
                "last_sync": now,
            })
        if create_unknown:
            for username, data in remote.items():
                local_part, _sep, mb_domain = username.partition("@")
                self.create({
                    "local_part": local_part,
                    "domain": mb_domain,
                    "name": data.get("name") or local_part,
                    "mailbox_active": str(data.get("active", "1")) == "1",
                    "quota_mb": int(data.get("quota") or 0) // BYTES_PER_MIB or 1024,
                    "quota_used_mb": int(data.get("quota_used") or 0) // BYTES_PER_MIB,
                    "state": "synced",
                    "last_sync": now,
                    "provision_smtp": False,
                    "provision_fetchmail": False,
                })

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def unlink(self):
        if any(rec.state == "synced" for rec in self):
            raise UserError(_(
                "These records track live Mailcow mailboxes. Deleting them "
                "in Odoo does NOT delete the mailbox in Mailcow and would "
                "desynchronise the two systems. Disable the mailbox instead, "
                "or remove it in the Mailcow admin UI first and re-sync."))
        return super().unlink()
