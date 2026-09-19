import logging

from odoo import http

_logger = logging.getLogger(__name__)

INTEGRATION_GROUP = "sgc_kartatap_bridge.group_kartatap_integration"

# RETIRED 2026-09-19 (KartaTap findings register, Phase 5 controller-retirement
# item). Confirmed zero callers: searched the KartaTap Next.js repo (master and
# the Odoo-billing-integration branch), every Odoo module tree on the VPS, and
# this module's own source — the only reference to "/kartatap/checkout" was
# this route's own definition. The supported, and only, production integration
# path is the native Odoo JSON-2 method:
#   POST /json/2/kartatap.checkout/create_or_get_kartatap_checkout
# This route is kept (not deleted) and now returns an explicit 410-equivalent
# retired response rather than executing the checkout, so a caller nobody
# noticed is told clearly why it stopped working instead of getting a bare
# 404 or, worse, still working as an unreviewed second auth path into the
# same business method. Do not restore this as a real entry point without a
# reviewed decision — see the register for the rationale.


class KartatapBridgeController(http.Controller):
    @http.route(
        "/kartatap/checkout",
        type="jsonrpc",
        auth="user",
        methods=["POST"],
        csrf=False,
        save_session=False,
    )
    def kartatap_checkout(self, **payload):
        _logger.info(
            "kartatap_checkout: retired route called by uid=%s — no payload processed",
            http.request.env.user.id,
        )
        return {
            "ok": False,
            "error": "retired",
            "message": (
                "This endpoint is retired. Use the native Odoo JSON-2 method: "
                "POST /json/2/kartatap.checkout/create_or_get_kartatap_checkout"
            ),
        }
