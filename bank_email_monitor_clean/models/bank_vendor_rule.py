from odoo import fields, models


class BankVendorRule(models.Model):
    _name = "bank.vendor.rule"
    _description = "Bank Vendor Parsing Rule"
    _order = "sequence, id"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    is_learning_draft = fields.Boolean(default=False, index=True)
    source_transaction_id = fields.Many2one(
        "bank.email.transaction",
        string="Source Transaction",
        readonly=True,
        ondelete="set null",
    )
    learning_confidence = fields.Float(readonly=True)

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )

    pattern = fields.Char(
        string="Email Content Regex",
        required=True,
        help="Regex matched against email subject + body.",
    )
    sender_pattern = fields.Char(
        string="Sender Regex",
        help="Optional regex matched against sender email.",
    )

    transaction_type = fields.Selection(
        [("credit", "Credit"), ("debit", "Debit")],
        string="Forced Transaction Type",
    )
    payment_method = fields.Selection(
        [
            ("credit_card", "Credit Card"),
            ("debit_card", "Debit Card"),
            ("bank_transfer", "Bank Transfer"),
            ("cash_deposit", "Cash Deposit"),
            ("cheque", "Cheque"),
            ("other", "Other"),
        ],
        string="Forced Payment Method",
    )
    expense_category = fields.Char()

    partner_id = fields.Many2one("res.partner", ondelete="set null")
    bank_journal_id = fields.Many2one(
        "account.journal",
        domain=[("type", "=", "bank")],
        check_company=True,
        ondelete="set null",
    )
    suggested_account_id = fields.Many2one(
        "account.account",
        check_company=True,
        ondelete="set null",
    )
    currency_id = fields.Many2one("res.currency", ondelete="set null")

    notes = fields.Text()
