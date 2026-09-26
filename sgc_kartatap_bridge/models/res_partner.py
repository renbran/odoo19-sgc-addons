import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Adds the immutable KartaTap tenant identifier to the partner.

    Business partners are matched ONLY on this identifier. Company names and email
    addresses change; the KartaTap tenant id does not. The column is nullable so that
    every pre-existing partner stays valid, and PostgreSQL treats multiple NULLs as
    distinct, so the unique constraint does not collide on unmapped partners.
    """

    _inherit = "res.partner"

    kartatap_company_id = fields.Char(
        string="KartaTap Company ID",
        index=True,
        copy=False,
        help="Immutable KartaTap tenant identifier. Never reuse or repurpose it.",
    )

    # Odoo 19: table constraints are declared with models.Constraint (the attribute name
    # becomes the PostgreSQL constraint name); the legacy `_sql_constraints` list is
    # silently ignored, so a unique guard written that way would not exist in the database.
    _kartatap_company_id_uniq = models.Constraint(
        "unique(kartatap_company_id)",
        "A partner is already linked to this KartaTap company ID.",
    )
