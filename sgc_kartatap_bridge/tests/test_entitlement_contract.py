from datetime import datetime

from odoo.tests.common import BaseCase, tagged

from ..lib import entitlement_contract as contract

# Golden vector computed with KartaTap's receiver (src/lib/odoo-billing/entitlements.ts:
# computeSignature, parseEntitlementEvent). If these drift, events are rejected as
# `invalid_signature` in production, so the bytes are pinned here exactly.
GOLDEN_SECRET = "test-secret-0123456789abcdef0123456789abcdef"
GOLDEN_TIMESTAMP = "1790000000"
GOLDEN_BODY = (
    '{"effective_period_end":"2026-10-26T00:00:00.000Z",'
    '"event_id":"odoo:ab12cd34:so42:activated",'
    '"event_type":"subscription.activated",'
    '"kartatap_company_id":"cmp_test_0001",'
    '"occurred_at":"2026-09-26T10:00:00.001Z",'
    '"odoo_partner_ref":"res.partner:7",'
    '"odoo_subscription_ref":"sale.order:42",'
    '"plan_code":"TEAM","quantity":3,"reason_code":null,'
    '"schema_version":1,"source":"odoo","status":"active"}'
)
GOLDEN_SIGNATURE = "4a3e917f7f5d715cf011fc7dc96753c88feb95e39f06ee7be1010bf595c58839"


def _golden_payload(**overrides):
    args = dict(
        event_id="odoo:ab12cd34:so42:activated",
        event_type="subscription.activated",
        occurred_at=datetime(2026, 9, 26, 10, 0, 0, 1000),
        kartatap_company_id="cmp_test_0001",
        plan_code="TEAM",
        quantity=3,
        odoo_partner_ref="res.partner:7",
        odoo_subscription_ref="sale.order:42",
        effective_period_end=datetime(2026, 10, 26),
    )
    args.update(overrides)
    return contract.build_payload(**args)


@tagged("post_install", "-at_install", "kartatap_bridge")
class TestEntitlementContract(BaseCase):
    def test_body_matches_receiver_golden_bytes(self):
        self.assertEqual(contract.serialize(_golden_payload()), GOLDEN_BODY)

    def test_signature_matches_receiver(self):
        self.assertEqual(contract.sign(GOLDEN_SECRET, GOLDEN_TIMESTAMP, GOLDEN_BODY), GOLDEN_SIGNATURE)
        headers = contract.headers(GOLDEN_SECRET, GOLDEN_TIMESTAMP, GOLDEN_BODY, "odoo:ab12cd34:so42:activated")
        self.assertEqual(headers["x-kartatap-signature"], "v1=" + GOLDEN_SIGNATURE)
        self.assertEqual(headers["x-kartatap-timestamp"], GOLDEN_TIMESTAMP)
        self.assertEqual(headers["x-kartatap-event-id"], "odoo:ab12cd34:so42:activated")

    def test_status_follows_event_type(self):
        self.assertEqual(_golden_payload(event_type="subscription.renewed")["status"], "active")
        self.assertEqual(_golden_payload(event_type="subscription.past_due")["status"], "past_due")
        self.assertEqual(_golden_payload(event_type="subscription.canceled")["status"], "canceled")

    def test_payloads_the_receiver_would_refuse_are_rejected_here(self):
        bad = [
            dict(event_type="subscription.teleported"),
            dict(event_id="short"),
            dict(event_id="has space in it"),
            dict(kartatap_company_id="bad/id"),
            dict(plan_code="GOLD"),
            dict(plan_code="TEAM", quantity=1),
            dict(quantity=101),
            dict(quantity=True),
            dict(odoo_subscription_ref="SO/2026/0001"),
            dict(odoo_subscription_ref=None),
            dict(reason_code="not allowed!"),
        ]
        for overrides in bad:
            with self.subTest(overrides=overrides):
                with self.assertRaises(contract.ContractError):
                    _golden_payload(**overrides)

    def test_cancellation_may_omit_the_subscription_reference(self):
        payload = _golden_payload(event_type="subscription.canceled", odoo_subscription_ref=None)
        self.assertIsNone(payload["odoo_subscription_ref"])

    def test_classification(self):
        for code in (200, 201, 204):
            self.assertEqual(contract.classify(code), "sent")
        for code in (None, 408, 429, 500, 502, 503, 504):
            self.assertEqual(contract.classify(code), "retry")
        for code in (301, 302, 400, 401, 403, 404, 409, 413, 422):
            self.assertEqual(contract.classify(code), "reject")

    def test_backoff_is_bounded_and_increasing(self):
        delays = [contract.backoff_seconds(n) for n in range(1, contract.MAX_ATTEMPTS + 3)]
        self.assertEqual(delays[0], 60)
        self.assertEqual(delays, sorted(delays))
        self.assertEqual(max(delays), contract.BACKOFF_SECONDS[-1])
