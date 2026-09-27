from datetime import date, datetime

from odoo.tests import TransactionCase, tagged

from ..lib import contract


@tagged("post_install", "-at_install", "layer3")
class TestContract(TransactionCase):
    def _payload(self, **kw):
        values = dict(
            event_id="odoo:abcd1234:so1:v1",
            occurred_at=datetime(2026, 10, 1, 8, 0, 0, 123000),
            tenant_slug="marinacrest",
            version=1,
            state="active",
            reason="paid",
            docs_status="pending",
            users=7,
            order_ref="sale.order/1",
            company_name="Marina Crest Real Estate LLC",
            billing_url="https://app.sgctech.ai/my/layer3/1?access_token=x",
            licence_expiry=date(2027, 5, 6),
            provision=True,
            admin_email="ops@marinacrest.ae",
            admin_name="A. Rahman",
        )
        values.update(kw)
        return contract.build_payload(**values)

    def test_payload_shape(self):
        p = self._payload()
        self.assertEqual(p["event_type"], "tenant.sync")
        self.assertEqual(p["occurred_at"], "2026-10-01T08:00:00.123Z")
        self.assertEqual(p["licence_expiry"], "2027-05-06")
        self.assertTrue(p["provision"])

    def test_admin_fields_only_on_provision(self):
        p = self._payload(provision=False)
        self.assertIsNone(p["admin_email"])
        self.assertIsNone(p["admin_name"])

    def test_rejects_bad_values(self):
        for bad in (
            {"tenant_slug": "Bad_Slug"},
            {"tenant_slug": "a"},
            {"state": "suspended"},
            {"docs_status": "maybe"},
            {"version": 0},
            {"users": 0},
            {"billing_url": "http://insecure"},
            {"admin_email": "not-an-email"},
        ):
            with self.subTest(bad=bad), self.assertRaises(contract.ContractError):
                self._payload(**bad)

    def test_signature_matches_reference(self):
        body = contract.serialize(self._payload())
        sig = contract.sign("s" * 32, "1790000000", body)
        self.assertEqual(len(sig), 64)
        self.assertEqual(contract.headers("s" * 32, 1790000000, body, "e1234567")["x-sgc-signature"], "v1=" + sig)
        self.assertNotEqual(sig, contract.sign("t" * 32, "1790000000", body))

    def test_classify(self):
        self.assertEqual(contract.classify(None), "retry")
        self.assertEqual(contract.classify(200), "sent")
        self.assertEqual(contract.classify(409), "reject")
        self.assertEqual(contract.classify(429), "retry")
        self.assertEqual(contract.classify(503), "retry")
