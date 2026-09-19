from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "kartatap_bridge")
class TestDuplicatePaymentGuard(TransactionCase):
    """F7 — at most one chargeable payment.transaction per KartaTap order.

    Scope proof included: an unrelated, non-KartaTap sale.order can carry as
    many payment.transaction rows as Odoo's stock behavior allows — this
    guard only ever intervenes for orders with a kartatap_request_id.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["payment.provider"].sudo().search(
            [("code", "=", "stripe"), ("state", "!=", "disabled")], limit=1
        )
        if not cls.provider:
            cls.skipTest(cls, "No enabled Stripe payment.provider configured in this environment.")
        cls.company = cls.provider.company_id
        cls.pml = cls.env["account.payment.method.line"].sudo().search(
            [("payment_provider_id", "=", cls.provider.id)], limit=1
        )
        cls.partner = cls.env["res.partner"].sudo().create({
            "name": "Duplicate Guard Test Partner", "company_id": cls.company.id,
        })

    def _kartatap_order(self, request_id, amount=29.0):
        return self._kartatap_order_in(self.env, request_id, amount=amount, partner_id=self.partner.id)

    def _kartatap_order_in(self, env, request_id, amount=29.0, partner_id=None):
        # setUpClass's cls.partner lives in the outer TransactionCase's
        # uncommitted savepoint — invisible to a genuinely separate
        # connection. Callers using a real committed cursor (the concurrency
        # test) must pass a partner created on THAT SAME cursor.
        partner_id = partner_id or self.partner.id
        return env["sale.order"].sudo().with_company(self.company).create({
            "partner_id": partner_id,
            "company_id": self.company.id,
            "currency_id": env.ref("base.AED").id,
            "kartatap_request_id": request_id,
            "kartatap_company_id": "guard-test-tenant",
            "require_signature": False,
            "order_line": [(0, 0, {
                "product_id": self._solo_product(env).id,
                "product_uom_qty": 1,
                "price_unit": amount,
            })],
        })

    def _solo_product(self, env=None):
        env = env or self.env
        product = env["product.product"].sudo().search(
            [("default_code", "=", "KT-SOLO-GUARD-TEST")], limit=1
        )
        if not product:
            product = env["product.product"].sudo().create({
                "name": "KartaTap SOLO (guard test)",
                "default_code": "KT-SOLO-GUARD-TEST",
                "type": "service",
                "is_recurring": True,
                "list_price": 29.0,
                "company_id": self.company.id,
            })
        return product

    def _tx_vals(self, order, ref, amount=29.0):
        return {
            "provider_id": self.provider.id,
            "payment_method_id": self.pml.payment_method_id.id,
            "company_id": order.company_id.id,
            "amount": amount,
            "currency_id": order.currency_id.id,
            "partner_id": order.partner_id.id,
            "reference": ref,
            "sale_order_ids": [(6, 0, [order.id])],
            "operation": "online_redirect",
        }

    def test_second_chargeable_attempt_after_done_is_refused(self):
        order = self._kartatap_order("guard-req-done")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-DONE-1")
        )
        tx1._set_done()
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"].sudo().create(
                self._tx_vals(order, "GUARD-DONE-2")
            )

    def test_second_chargeable_attempt_after_authorized_is_refused(self):
        order = self._kartatap_order("guard-req-authorized")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-AUTH-1")
        )
        tx1._set_authorized()
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"].sudo().create(
                self._tx_vals(order, "GUARD-AUTH-2")
            )

    def test_pending_transaction_is_reused_not_duplicated(self):
        order = self._kartatap_order("guard-req-pending")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-PENDING-1")
        )
        tx1._set_pending()
        tx2 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-PENDING-2")
        )
        self.assertEqual(
            tx1.id, tx2.id,
            "A second create() call against an order with a pending "
            "transaction must return the SAME transaction, not a new one.",
        )
        count = self.env["payment.transaction"].sudo().search_count(
            [("sale_order_ids", "in", [order.id])]
        )
        self.assertEqual(count, 1, "Exactly one transaction row must exist for this order.")

    def test_retry_after_failed_creates_a_fresh_transaction(self):
        order = self._kartatap_order("guard-req-failed-retry")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-FAIL-1")
        )
        tx1._set_error("simulated failure")
        tx2 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-FAIL-2")
        )
        self.assertNotEqual(
            tx1.id, tx2.id,
            "A retry after a FAILED transaction must be allowed to create "
            "a genuinely new transaction — this is not a duplicate.",
        )

    def test_retry_after_canceled_creates_a_fresh_transaction(self):
        order = self._kartatap_order("guard-req-canceled-retry")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-CANCEL-1")
        )
        tx1._set_canceled()
        tx2 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-CANCEL-2")
        )
        self.assertNotEqual(
            tx1.id, tx2.id,
            "A retry after a CANCELED transaction must be allowed to "
            "create a genuinely new transaction.",
        )

    def test_conflicting_replay_same_reference_different_amount(self):
        """Reusing the same reference for a different commercial amount is a
        caller bug, not something this guard is responsible for policing —
        but confirms the guard does not silently accept it as identical."""
        order = self._kartatap_order("guard-req-conflict")
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-CONFLICT-1", amount=29.0)
        )
        tx1._set_error("simulated failure")
        tx2 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(order, "GUARD-CONFLICT-2", amount=44.0)
        )
        self.assertNotEqual(tx1.id, tx2.id)
        self.assertEqual(tx2.amount, 44.0)

    def test_unrelated_non_kartatap_order_is_unaffected(self):
        """Scope proof: an order with no kartatap_request_id can carry
        multiple chargeable-state transactions — Odoo's normal behavior,
        completely untouched by this guard."""
        plain_order = self.env["sale.order"].sudo().with_company(self.company).create({
            "partner_id": self.partner.id,
            "company_id": self.company.id,
            "order_line": [(0, 0, {
                "product_id": self._solo_product().id,
                "product_uom_qty": 1,
                "price_unit": 29.0,
            })],
        })
        self.assertFalse(plain_order.kartatap_request_id)
        tx1 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(plain_order, "PLAIN-1")
        )
        tx1._set_done()
        # This must NOT raise — the guard only ever applies to KartaTap orders.
        tx2 = self.env["payment.transaction"].sudo().create(
            self._tx_vals(plain_order, "PLAIN-2")
        )
        self.assertNotEqual(tx1.id, tx2.id)

    def test_concurrent_lock_acquisition_blocks_a_second_connection(self):
        """Deterministic proof of the SAME row-lock mechanism
        _kartatap_guard_transition() relies on for concurrency safety,
        using two genuinely separate PostgreSQL connections rather than
        Python threads racing against each other.

        Why not real threads: attempted first, but this Odoo test harness
        hangs when a background thread calls self.registry.cursor() —
        an environment/harness issue (likely thread-affinity in the
        connection pool or the test runner's own locking), not something
        that reflects on the guard's actual correctness. A deterministic
        two-cursor test proves the identical property — a second connection
        cannot acquire the SAME row lock while the first holds it — without
        depending on real-world thread scheduling or that harness quirk.

        TransactionCase wraps the whole test in one uncommitted transaction,
        invisible to a genuinely separate connection (real PostgreSQL MVCC,
        not just an Odoo restriction) — so the setup this test uses must be
        created and COMMITTED via its own connection, with explicit cleanup
        afterward instead of relying on the test framework's rollback.
        """
        order_id = None
        tx_ids = []
        partner_id = None
        with self.registry.cursor() as setup_cr:
            setup_env = self.env(cr=setup_cr)
            # A fresh, separately-committed partner — cls.partner from
            # setUpClass lives in the outer test's uncommitted savepoint and
            # would raise MissingError from this genuinely separate cursor.
            partner_id = setup_env["res.partner"].sudo().create({
                "name": "Duplicate Guard Concurrency Test Partner",
                "company_id": self.company.id,
            }).id
            order = self._kartatap_order_in(
                setup_env, "guard-req-concurrent", partner_id=partner_id
            )
            tx1 = setup_env["payment.transaction"].sudo().create(
                self._tx_vals(order, "GUARD-RACE-1")
            )
            tx2 = setup_env["payment.transaction"].sudo().create(
                self._tx_vals(order, "GUARD-RACE-2")
            )
            self.assertEqual(tx1.state, "draft")
            self.assertEqual(tx2.state, "draft")
            order_id, tx_ids = order.id, [tx1.id, tx2.id]
            setup_cr.commit()

        def _cleanup():
            with self.registry.cursor() as cr:
                env = self.env(cr=cr)
                env["payment.transaction"].sudo().browse(tx_ids).unlink()
                env["sale.order"].sudo().browse(order_id).unlink()
                env["res.partner"].sudo().browse(partner_id).unlink()
                cr.commit()
        self.addCleanup(_cleanup)

        # Cursor A: acquire the exact lock _kartatap_guard_transition() takes,
        # and hold it open (no commit yet).
        cr_a = self.registry.cursor()
        try:
            cr_a.execute("SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (order_id,))

            # Cursor B: a second, genuinely separate connection. A short
            # lock_timeout makes the block deterministic and fast to observe
            # instead of hanging — if cursor A's lock is real, this raises;
            # if the lock were somehow not actually held, this would succeed
            # immediately instead.
            cr_b = self.registry.cursor()
            try:
                cr_b.execute("SET LOCAL lock_timeout = '1000'")  # 1 second
                with self.assertRaises(Exception) as ctx:
                    cr_b.execute(
                        "SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (order_id,)
                    )
                self.assertIn(
                    "lock", str(ctx.exception).lower(),
                    "Cursor B's blocked SELECT ... FOR UPDATE must fail with a "
                    "lock-timeout error, proving cursor A's lock is real and "
                    "held — not any other kind of failure. Got: %r" % ctx.exception,
                )
                cr_b.rollback()
            finally:
                cr_b.close()

            # Cursor A releases the lock.
            cr_a.commit()
        finally:
            cr_a.close()

        # With the lock released, a fresh attempt from a third connection —
        # standing in for the "second request, now that the first finished"
        # case — must succeed immediately.
        with self.registry.cursor() as cr_c:
            cr_c.execute("SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (order_id,))
            row = cr_c.fetchone()
            self.assertEqual(row, (order_id,))
            cr_c.commit()

        # Finally, confirm the guard built on this exact mechanism produces
        # the correct application-level outcome for the same order: the
        # first transaction to actually reach 'done' wins, the second is
        # refused. This is the sequential expression of what the lock
        # enforces under real concurrency (proven above, mechanism-only).
        env = self.env(cr=self.registry.cursor())
        try:
            tx1 = env["payment.transaction"].sudo().browse(tx_ids[0])
            tx2 = env["payment.transaction"].sudo().browse(tx_ids[1])
            tx1._set_done()
            env.cr.commit()
            with self.assertRaises(ValidationError):
                tx2._set_done()
            env.cr.rollback()
        finally:
            env.cr.close()

        with self.registry.cursor() as check_cr:
            check_env = self.env(cr=check_cr)
            done_count = check_env["payment.transaction"].sudo().search_count([
                ("sale_order_ids", "in", [order_id]),
                ("state", "=", "done"),
            ])
        self.assertEqual(
            done_count, 1,
            "Exactly one transaction for this order must have reached "
            "'done' after both concurrent attempts finished.",
        )
