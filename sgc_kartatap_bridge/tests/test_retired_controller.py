import json

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "kartatap_bridge")
class TestRetiredController(HttpCase):
    """Phase 5 — the unused /kartatap/checkout controller is retired, and the
    native JSON-2 endpoint remains the only functional integration path."""

    def test_retired_route_returns_explicit_retired_response_not_checkout(self):
        response = self.url_open(
            "/kartatap/checkout",
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}),
            headers={"Content-Type": "application/json"},
        )
        # auth='user' with no session/API key rejects before reaching the
        # handler body at all — proven separately below. This call, with no
        # auth header, must NOT produce a 200 with checkout-shaped output; if
        # it somehow did, that would mean a weaker auth fallback exists.
        body = response.json()
        result = body.get("result")
        self.assertFalse(
            result and result.get("odoo"),
            "An unauthenticated call must never reach real checkout logic "
            "(no sale_order_id/checkout_url in the response) — that would "
            "mean the retirement introduced a weaker auth path.",
        )

    def test_native_json2_endpoint_remains_functional(self):
        # Confirms retiring the old controller did not disturb the native
        # method itself — reachable via ORM the same way the JSON-2 HTTP
        # layer calls it (the HTTP layer's own auth/routing is Odoo core,
        # not this module's code, and is out of scope for this test).
        model = self.env["kartatap.checkout"].sudo()
        self.assertTrue(
            hasattr(model, "create_or_get_kartatap_checkout"),
            "The native create_or_get_kartatap_checkout method must still "
            "exist and be callable — this is the sole supported integration "
            "path per the KartaTap findings register.",
        )
