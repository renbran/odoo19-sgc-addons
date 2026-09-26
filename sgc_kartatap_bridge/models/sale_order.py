import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Links an Odoo quotation/subscription to the KartaTap request that created it.

    `kartatap_request_id` is the idempotency key supplied by KartaTap: a replayed
    request must return the SAME quotation instead of creating a second one. It is
    nullable (every existing order stays valid) and unique when set, so the database -
    not application logic - is the last line of defence against duplicates.
    """

    _inherit = "sale.order"

    kartatap_request_id = fields.Char(
        string="KartaTap Request ID",
        index=True,
        copy=False,
        help="Idempotency key of the KartaTap checkout request that created this order.",
    )
    kartatap_company_id = fields.Char(
        string="KartaTap Company ID",
        index=True,
        copy=False,
        help="KartaTap tenant identifier this order was created for.",
    )

    # Odoo 19: declared with models.Constraint; `_sql_constraints` is ignored, which would
    # have left idempotency protected only by application logic instead of by the database.
    _kartatap_request_id_uniq = models.Constraint(
        "unique(kartatap_request_id)",
        "An order already exists for this KartaTap request ID.",
    )
