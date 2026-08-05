# -*- coding: utf-8 -*-
import json
import logging
import secrets
import string

from odoo import _, http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

WEBHOOK_SECRET_PARAM = "sgc_mailcow.webhook_secret"
ROLEPLAY_CHANNEL_PARAM = "sgc_mailcow.roleplay_channel_id"


class RoleplayPassWebhookController(http.Controller):
    """Receives the 'hire passed Roleplay Arena' event from the external
    AI-persona platform and provisions the hire's credentials:

      * a Mailcow mailbox (sgctech.ai) with a temporary password, and
      * an Odoo ``res.users`` login using the same temporary password.

    Plain HTTP + JSON (not Odoo's ``type="json"`` envelope) so a non-Odoo
    caller can POST a normal JSON payload, mirroring ``sgc_cip_bridge``.
    """

    def _json_response(self, payload, status=200):
        return Response(json.dumps(payload), status=status, content_type="application/json")

    def _gen_password(self):
        alphabet = string.ascii_letters + string.digits
        return (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.digits)
            + "".join(secrets.choice(alphabet) for _ in range(14))
        )

    @http.route(
        "/sgc-webhook/roleplay-pass",
        type="http",
        auth="public",
        csrf=False,
        methods=["POST"],
    )
    def roleplay_pass(self, **kwargs):
        env = request.env

        # --- Auth -------------------------------------------------------
        icp = env["ir.config_parameter"].sudo()
        expected_secret = icp.get_param(WEBHOOK_SECRET_PARAM)
        provided_secret = request.httprequest.headers.get("X-SGC-Webhook-Secret")
        if not expected_secret or provided_secret != expected_secret:
            _logger.warning(
                "Rejected roleplay-pass webhook from %s: invalid or missing secret",
                request.httprequest.remote_addr,
            )
            return self._json_response(
                {"status": "error", "message": "Unauthorized"}, status=401
            )

        # --- Parse ------------------------------------------------------
        # Contract mirrors the roleplay-arena.vercel.app frontend, which POSTs
        # to /api/booking/provision with:
        #   {fullName, email, mobile, personaId, sessionId, bookingToken}
        # The simpler aliases (name/role/phone) are accepted as well.
        try:
            payload = request.httprequest.get_json(force=True)
        except Exception:
            return self._json_response(
                {"status": "error", "message": "Invalid JSON body"}, status=400
            )

        email = (payload.get("email") or "").strip().lower()
        name = (payload.get("fullName") or payload.get("name") or "").strip()
        role = (payload.get("personaId") or payload.get("role") or "").strip()
        phone = (payload.get("mobile") or payload.get("phone") or "").strip()
        session_id = (payload.get("sessionId") or "").strip()
        booking_token = (payload.get("bookingToken") or "").strip()
        dry_run = bool(payload.get("dry_run"))

        if not email or not name:
            return self._json_response(
                {
                    "status": "error",
                    "message": "Missing required fields: email, name",
                },
                status=400,
            )

        default_domain = (
            icp.get_param("sgc_mailcow.default_domain") or "sgctech.ai"
        ).strip().lower()
        email_local, sep, email_domain = email.partition("@")

        # --- Partner ----------------------------------------------------
        Partner = env["res.partner"].sudo()
        partner = Partner.search([("email", "=", email)], limit=1)
        if not partner:
            partner = Partner.search([("name", "=ilike", name)], limit=1)
        if not partner:
            partner = Partner.create(
                {"name": name, "email": email, "phone": phone or False}
            )

        # --- Idempotency: existing Odoo user / mailbox ------------------
        Users = env["res.users"].sudo()
        user = Users.search([("login", "=", email)], limit=1)
        Mailbox = env["mailcow.mailbox"].sudo()
        existing_mailbox = Mailbox.search(
            [("local_part", "=", email_local), ("domain", "=", email_domain)],
            limit=1,
        )

        if user or existing_mailbox:
            return self._json_response(
                {
                    "status": "success",
                    "already_provisioned": True,
                    "odoo_user_id": user.id if user else False,
                    "odoo_login": user.login if user else False,
                    "mailbox_email": existing_mailbox.email if existing_mailbox else False,
                    "dry_run": dry_run,
                }
            )

        # --- Credential generation --------------------------------------
        password = self._gen_password()
        mailbox = False
        mailbox_created = False

        if not dry_run:
            # 1) Mailcow mailbox first (a Mailcow failure aborts before the
            #    Odoo user exists without credentials).
            if email_domain == default_domain:
                mailbox = Mailbox.create(
                    {
                        "local_part": email_local,
                        "domain": email_domain,
                        "name": name,
                        "password": password,
                        "force_pw_update": True,
                        "provision_smtp": False,
                        "provision_fetchmail": False,
                    }
                )
                mailbox.action_create_in_mailcow()
                mailbox_created = True
            else:
                _logger.warning(
                    "Roleplay-pass: email %s is not under %s; skipping Mailcow mailbox",
                    email,
                    default_domain,
                )

            # 2) Odoo user (skip auto-provision so we don't double-create).
            try:
                user = Users.with_context(mailcow_no_autoprovision=True).create(
                    {
                        "name": name,
                        "login": email,
                        "password": password,
                        "email": email,
                        "partner_id": partner.id,
                        "groups_id": [(6, 0, [env.ref("base.group_portal").id])],
                    }
                )
            except Exception as exc:
                _logger.exception("Failed to create Odoo user for %s", email)
                if mailbox:
                    try:
                        mailbox.unlink()
                    except Exception:
                        _logger.exception("Failed to roll back mailbox %s", email)
                return self._json_response(
                    {
                        "status": "error",
                        "message": "Failed to create Odoo user: %s" % exc,
                    },
                    status=500,
                )

            if mailbox:
                mailbox.write({"user_id": user.id})
                mailbox.message_post(
                    body=_(
                        "Odoo user %(login)s linked to mailbox. Temporary password "
                        "delivered by the onboarding platform.",
                        login=user.login,
                    )
                )

        # 3) Record Roleplay Arena completion (best-effort, DB-level).
        completion_recorded = False
        try:
            channel_id = int(icp.get_param(ROLEPLAY_CHANNEL_PARAM, "6"))
            cp_env = env["slide.channel.partner"]
            cp = cp_env.search(
                [("channel_id", "=", channel_id), ("partner_id", "=", partner.id)],
                limit=1,
            )
            if cp:
                cp.write({"completion": 100, "member_status": "completed"})
                completion_recorded = True
            else:
                channel = env["slide.channel"].sudo().browse(channel_id)
                total = channel.total_slides or 0
                cp_env.create(
                    {
                        "channel_id": channel_id,
                        "partner_id": partner.id,
                        "completion": 100,
                        "completed_slides_count": total,
                        "member_status": "completed",
                    }
                )
                completion_recorded = True
        except Exception:
            _logger.exception(
                "Roleplay-pass: could not record channel-%s completion for %s",
                ROLEPLAY_CHANNEL_PARAM,
                email,
            )

        result = {
            "status": "success",
            "already_provisioned": False,
            "dry_run": dry_run,
            "role": role or False,
            "session_id": session_id or False,
            "odoo_user_id": user.id if user else False,
            "odoo_login": user.login if user else False,
            "mailbox_email": mailbox.email if mailbox else False,
            "mailbox_created": mailbox_created,
            "roleplay_completion_recorded": completion_recorded,
        }
        if not dry_run:
            result["temporary_password"] = password

        _logger.info(
            "Roleplay-pass: provisioned %s (odoo_user_id=%s, mailbox=%s, role=%s, session=%s)",
            email,
            user.id if user else None,
            mailbox.email if mailbox else None,
            role,
            session_id,
        )
        return self._json_response(result)
