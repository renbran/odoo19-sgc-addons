from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mailcow_base_url = fields.Char(
        string="Mailcow URL",
        config_parameter="sgc_mailcow.base_url",
        help="Root URL of the Mailcow UI, e.g. https://mail.sgctech.ai")
    mailcow_api_key = fields.Char(
        string="Mailcow API Key",
        config_parameter="sgc_mailcow.api_key",
        help="Read-write API key from Mailcow admin → Access → API.")
    mailcow_default_domain = fields.Char(
        string="Default Mail Domain",
        config_parameter="sgc_mailcow.default_domain",
        help="Domain new mailboxes are created under, e.g. sgctech.ai")
    mailcow_default_quota_mb = fields.Integer(
        string="Default Quota (MB)",
        config_parameter="sgc_mailcow.default_quota_mb",
        default=3072)
    mailcow_mail_host = fields.Char(
        string="SMTP/IMAP Host Override",
        config_parameter="sgc_mailcow.mail_host",
        help="Hostname used when provisioning Odoo mail servers. "
             "Leave empty to use the Mailcow URL host.")
    mailcow_auto_provision = fields.Boolean(
        string="Auto-provision mailboxes for new users",
        config_parameter="sgc_mailcow.auto_provision",
        help="When enabled, creating an internal user whose email domain "
             "matches the default mail domain automatically creates a Mailcow "
             "mailbox (mailbox only, no Odoo SMTP/IMAP server). Off by default.")

    mailcow_webhook_secret = fields.Char(
        string="Roleplay Pass Webhook Secret",
        config_parameter="sgc_mailcow.webhook_secret",
        help="Shared secret the external AI-persona platform sends in the "
             "X-SGC-Webhook-Secret header when a hire passes the Roleplay "
             "Arena, triggering Mailcow + Odoo credential provisioning.")
    mailcow_roleplay_channel_id = fields.Integer(
        string="Roleplay Arena Channel ID",
        config_parameter="sgc_mailcow.roleplay_channel_id",
        default=6,
        help="slide.channel id of the Roleplay Arena; its completion is "
             "recorded when credentials are provisioned.")

    def action_mailcow_test_connection(self):
        self.env["mailcow.api"].test_connection()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Mailcow",
                "message": "Connection successful — API key accepted.",
                "type": "success",
                "sticky": False,
            },
        }
