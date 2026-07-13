import logging
import secrets
import string

from odoo import api, models, _

from .mailcow_mailbox import LOCAL_PART_RE

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------------------
    # Auto-provisioning on user creation
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        # Opt-out hook for scripted / bulk user creation.
        if not self.env.context.get("mailcow_no_autoprovision"):
            for user in users:
                # Fail-safe: never let mailbox provisioning break user creation.
                user._mailcow_try_autoprovision()
        return users

    def _mailcow_try_autoprovision(self):
        """Run provisioning inside a savepoint with a broad guard so a Mailcow
        outage or API error can never raise into the user-creation transaction."""
        self.ensure_one()
        try:
            with self.env.cr.savepoint():
                self._mailcow_autoprovision()
        except Exception:
            _logger.exception(
                "Mailcow auto-provision skipped for user %s (id %s)",
                self.login, self.id)

    def _mailcow_autoprovision(self, force=False):
        """Create and push a Mailcow mailbox for this user when every guardrail
        passes. ``force=True`` bypasses only the on/off setting (used by the
        manual backfill action); all other guards still apply."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        # Guard 1: global toggle (default off).
        if not force and icp.get_param("sgc_mailcow.auto_provision") not in (
                "True", "1", "true"):
            return
        # Guard 3: internal, active users only.
        if self.share or not self.active:
            return
        # Guard 4: domain must match the configured default domain.
        default_domain = (icp.get_param(
            "sgc_mailcow.default_domain") or "").strip().lower()
        if not default_domain:
            return
        # Derive the mailbox address from whichever identity (login first, then
        # email) actually sits under the configured domain. A user's login can be
        # the corporate address while their partner email is personal, or vice
        # versa; we provision only for the address under default_domain.
        local_part = None
        for candidate in (self.login, self.email):
            cand = (candidate or "").strip().lower()
            cand_local, sep, cand_domain = cand.partition("@")
            if sep and cand_local and cand_domain == default_domain:
                local_part = cand_local
                break
        if not local_part:
            return
        # Guard 7: local part must be valid for Mailcow.
        if not LOCAL_PART_RE.match(local_part):
            _logger.warning(
                "Mailcow: skipping %s — invalid local part %r",
                self.login, local_part)
            return
        # Guard 5: Mailcow connection configured.
        if not self.env["mailcow.api"].is_configured():
            _logger.warning(
                "Mailcow not configured; skipping provision for %s", addr)
            return
        # Guard 6: idempotency — never duplicate an existing mailbox record.
        Mailbox = self.env["mailcow.mailbox"].sudo()
        if Mailbox.search_count([
                ("local_part", "=", local_part),
                ("domain", "=", default_domain)]):
            return
        password = self._mailcow_generate_password()
        mailbox = Mailbox.create({
            "local_part": local_part,
            "domain": default_domain,
            "name": self.name,
            "password": password,
            "force_pw_update": True,
            "user_id": self.id,
            "employee_id": self.employee_id.id if self.employee_id else False,
            # Guard 8: mailbox-only — do not auto-create Odoo SMTP/IMAP servers.
            "provision_smtp": False,
            "provision_fetchmail": False,
        })
        # Post the temporary password to chatter before the push clears it.
        mailbox.message_post(body=_(
            "Auto-provisioned for new user %(login)s. Temporary password: "
            "%(pw)s (the user must change it on first login).",
            login=self.login, pw=password))
        mailbox.action_create_in_mailcow()
        _logger.info(
            "Mailcow: provisioned mailbox %s for user %s",
            mailbox.email, self.login)

    @api.model
    def _mailcow_generate_password(self):
        """Strong random password satisfying Mailcow's default policy
        (guarantees at least one uppercase letter and one digit)."""
        alphabet = string.ascii_letters + string.digits
        return (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.digits)
            + "".join(secrets.choice(alphabet) for _ in range(14)))

    def action_provision_mailbox(self):
        """Manual backfill for existing users (e.g. via the Users action menu).
        Bypasses only the on/off toggle; errors surface to the admin."""
        for user in self:
            user._mailcow_autoprovision(force=True)
        return True
