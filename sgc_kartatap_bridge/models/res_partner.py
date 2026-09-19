from odoo import fields, models


class ResPartner(models.Model):
    """Tags the partner record representing a KartaTap tenant company so
    kartatap.checkout can find (or create) exactly one partner per tenant
    instead of creating a duplicate on every checkout call.
    """

    _inherit = "res.partner"

    kartatap_company_id = fields.Char(
        string="KartaTap Company Id",
        index=True,
        help="KartaTap's own Company.id (Prisma cuid) for the tenant this "
        "partner represents. Set only by sgc_kartatap_bridge.",
    )

    _sql_constraints = [
        (
            "kartatap_company_id_unique",
            "unique(kartatap_company_id)",
            "A KartaTap company can only be linked to one partner.",
        ),
    ]
