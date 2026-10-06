from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # ── IMAP ─────────────────────────────────────────────────────────
    bank_monitor_imap_host = fields.Char(
        string="IMAP Host",
        config_parameter="bank_monitor.imap_host",
    )
    bank_monitor_imap_port = fields.Integer(
        string="IMAP Port",
        default=993,
        config_parameter="bank_monitor.imap_port",
    )
    bank_monitor_imap_user = fields.Char(
        string="IMAP Username",
        config_parameter="bank_monitor.imap_user",
    )
    bank_monitor_imap_pass = fields.Char(
        string="IMAP Password",
        config_parameter="bank_monitor.imap_pass",
    )
    bank_monitor_imap_folder = fields.Char(
        string="IMAP Folder",
        default="INBOX",
        config_parameter="bank_monitor.imap_folder",
    )
    bank_monitor_lookback_days = fields.Integer(
        string="Lookback Days",
        default=7,
        config_parameter="bank_monitor.lookback_days",
    )

    # ── Vendor rules ─────────────────────────────────────────────────
    bank_monitor_vendor_rules = fields.Text(
        string="Vendor Rules",
        help=(
            "One rule per line: Vendor Name|regex|transaction_type|payment_method|"
            "expense_category|account_name|sender_regex"
        ),
    )
    bank_monitor_default_bank_journal_id = fields.Many2one(
        "account.journal",
        string="Default Bank Journal",
        domain=[("type", "=", "bank")],
        config_parameter="bank_monitor.default_bank_journal_id",
    )

    # ── Automation ───────────────────────────────────────────────────
    bank_monitor_auto_post_threshold = fields.Integer(
        string="Auto-Confirm Confidence Threshold",
        default=95,
        config_parameter="bank_monitor.auto_post_threshold",
    )

    def get_values(self):
        res = super().get_values()
        res["bank_monitor_vendor_rules"] = (
            self.env["ir.config_parameter"].sudo().get_param("bank_monitor.vendor_rules", "")
        )
        return res

    def set_values(self):
        super().set_values()
        self.env["ir.config_parameter"].sudo().set_param(
            "bank_monitor.vendor_rules", self.bank_monitor_vendor_rules or ""
        )
