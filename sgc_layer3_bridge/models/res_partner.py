from odoo import fields, models


class ResPartner(models.Model):
    """The customer company of a Layer 3 tenant, matched on its tenant subdomain."""

    _inherit = "res.partner"

    l3_tenant_slug = fields.Char(
        string="Layer 3 Tenant",
        index=True,
        copy=False,
        help="Subdomain of this customer's Layer 3 workspace (<slug>.sgctech.ai). Never reuse it.",
    )

    # Odoo 19: `_sql_constraints` is ignored; table constraints use models.Constraint.
    _l3_tenant_slug_uniq = models.Constraint(
        "unique(l3_tenant_slug)",
        "A customer is already linked to this Layer 3 tenant.",
    )
