# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SgcAccountingCompany(models.Model):
    _name = "sgc.accounting.company"
    _description = "Accounting Client Company"
    _order = "client_id, name"

    client_id = fields.Many2one(
        "sgc.accounting.client",
        string="Accounting Client",
        required=True,
        ondelete="cascade",
        index=True,
    )
    odoo_company_id = fields.Integer(
        string="Odoo Company ID",
        required=True,
        help="res.company id inside the client database.",
    )
    name = fields.Char(required=True)
    trn = fields.Char(string="TRN", size=15)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )
    is_default = fields.Boolean(string="Default Company")
    active = fields.Boolean(default=True)
    last_sync_at = fields.Datetime(string="Last Synchronized")

    _company_uniq = models.Constraint(
        "unique(client_id, odoo_company_id)",
        "This company is already registered for the client.",
    )

    @api.constrains("trn")
    def _check_trn(self):
        for company in self:
            if company.trn and (
                len(company.trn) != 15 or not company.trn.isdigit()
            ):
                raise ValidationError(
                    _("A UAE TRN must contain exactly 15 digits.")
                )
