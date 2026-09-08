import logging
from urllib.parse import urlparse

import requests

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TIMEOUT = 20


class MailcowApi(models.AbstractModel):
    """Thin client for the Mailcow REST API (/api/v1/...).

    Credentials live in ir.config_parameter:
      - sgc_mailcow.base_url   e.g. https://mail.sgctech.ai
      - sgc_mailcow.api_key    read-write API key from the Mailcow admin UI
    """
    _name = "mailcow.api"
    _description = "Mailcow API Client"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @api.model
    def _get_params(self, raise_if_missing=True):
        icp = self.env["ir.config_parameter"].sudo()
        base_url = (icp.get_param("sgc_mailcow.base_url") or "").strip().rstrip("/")
        if base_url and not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url
        api_key = (icp.get_param("sgc_mailcow.api_key") or "").strip()
        if (not base_url or not api_key) and raise_if_missing:
            raise UserError(_(
                "Mailcow connection is not configured. Set the server URL "
                "and API key under Settings → General Settings → Mailcow."))
        return base_url, api_key

    @api.model
    def is_configured(self):
        base_url, api_key = self._get_params(raise_if_missing=False)
        return bool(base_url and api_key)

    @api.model
    def get_mail_host(self):
        """Hostname used for SMTP/IMAP provisioning (defaults to the API host)."""
        icp = self.env["ir.config_parameter"].sudo()
        host = icp.get_param("sgc_mailcow.mail_host")
        if host:
            return host.strip()
        base_url, _key = self._get_params()
        return urlparse(base_url).hostname

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------
    @api.model
    def _request(self, method, endpoint, payload=None):
        base_url, api_key = self._get_params()
        url = "%s%s" % (base_url, endpoint)
        headers = {"X-MAILCOW-API-Key": api_key, "Content-Type": "application/json"}
        try:
            resp = requests.request(
                method, url, json=payload, headers=headers, timeout=TIMEOUT)
        except requests.exceptions.RequestException as exc:
            raise UserError(_(
                "Could not reach Mailcow at %(url)s: %(error)s",
                url=base_url, error=exc))
        if resp.status_code == 401:
            raise UserError(_("Mailcow rejected the API key (401 Unauthorized)."))
        if resp.status_code == 403:
            raise UserError(_(
                "Mailcow denied access (403 Forbidden). Check that this "
                "server's IP address is in the Mailcow API allow-list."))
        if resp.status_code >= 400:
            raise UserError(_(
                "Mailcow API error %(code)s: %(body)s",
                code=resp.status_code, body=resp.text[:500]))
        try:
            return resp.json()
        except ValueError:
            raise UserError(_(
                "Mailcow returned a non-JSON response. Check that the URL "
                "points to the Mailcow root (e.g. https://mail.example.com)."))

    @api.model
    def _check_write_result(self, result, action):
        """add/edit endpoints return a list of {type, msg} dicts."""
        if not isinstance(result, list):
            result = [result] if result else []
        errors = []
        for item in result:
            if isinstance(item, dict) and item.get("type") not in ("success", None):
                msg = item.get("msg")
                if isinstance(msg, list):
                    msg = " ".join(str(m) for m in msg)
                errors.append(str(msg))
        if errors:
            raise UserError(_(
                "Mailcow refused to %(action)s: %(errors)s",
                action=action, errors="; ".join(errors)))
        return True

    # ------------------------------------------------------------------
    # High-level operations
    # ------------------------------------------------------------------
    @api.model
    def test_connection(self):
        """Cheap authenticated call; raises UserError on any failure."""
        data = self._request("GET", "/api/v1/get/status/containers")
        if not isinstance(data, dict) or not data:
            raise UserError(_(
                "Connected, but Mailcow returned an unexpected payload. "
                "The API key may be read-only or invalid."))
        return True

    @api.model
    def get_domains(self):
        data = self._request("GET", "/api/v1/get/domain/all")
        return data if isinstance(data, list) else []

    @api.model
    def get_mailboxes(self, domain):
        data = self._request("GET", "/api/v1/get/mailbox/all/%s" % domain)
        return data if isinstance(data, list) else []

    @api.model
    def get_mailbox(self, username):
        data = self._request("GET", "/api/v1/get/mailbox/%s" % username)
        return data if isinstance(data, dict) and data.get("username") else None

    @api.model
    def add_mailbox(self, vals):
        """vals keys: local_part, domain, name, password, quota (MiB),
        active, force_pw_update, tls_enforce_in, tls_enforce_out, tags."""
        payload = {
            "local_part": vals["local_part"],
            "domain": vals["domain"],
            "name": vals.get("name") or vals["local_part"],
            "password": vals["password"],
            "password2": vals["password"],
            "quota": str(vals.get("quota") or 1024),
            "active": "1" if vals.get("active", True) else "0",
            "force_pw_update": "1" if vals.get("force_pw_update") else "0",
            "tls_enforce_in": "1" if vals.get("tls_enforce_in") else "0",
            "tls_enforce_out": "1" if vals.get("tls_enforce_out") else "0",
        }
        if vals.get("tags"):
            payload["tags"] = vals["tags"]
        result = self._request("POST", "/api/v1/add/mailbox", payload)
        self._check_write_result(result, _("create the mailbox"))
        return True

    @api.model
    def edit_mailbox(self, usernames, attr):
        """attr: dict of mailbox attributes to change, e.g. {'active': '0'}."""
        if isinstance(usernames, str):
            usernames = [usernames]
        payload = {"items": usernames, "attr": attr}
        result = self._request("POST", "/api/v1/edit/mailbox", payload)
        self._check_write_result(result, _("update the mailbox"))
        return True

    @api.model
    def set_mailbox_active(self, usernames, active):
        return self.edit_mailbox(usernames, {"active": "1" if active else "0"})
