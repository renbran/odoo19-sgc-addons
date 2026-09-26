import logging

from odoo import api, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# A transaction in any of these states is "chargeable": either money is
# already captured (done), already authorized and awaiting capture
# (authorized), or a customer is actively mid-flow with a provider (pending).
# error/cancel/draft are NOT chargeable — a fresh attempt is always safe.
CHARGEABLE_STATES = ("pending", "authorized", "done")


class PaymentTransaction(models.Model):
    """Order-level duplicate-payment guard for KartaTap-originated orders only.

    Odoo's own generic payment flow allows any number of payment.transaction
    records against one sale.order — by design, since one order can legitimately
    be paid in installments or have a failed attempt followed by a retry. That
    generic behavior is exactly right for every OTHER business flow this Odoo
    instance runs. It is wrong specifically for KartaTap subscriptions, where
    "one order, at most one chargeable transaction at a time" is the required
    policy (F7 in the KartaTap findings register): a completed AED 29 payment
    must never be followed by a second, independent, also-successful one
    against the same order.

    Scope: only transactions linked to a sale.order that carries a
    kartatap_request_id (i.e. created by kartatap.checkout) are guarded here.
    Every other payment.transaction in this database is completely unaffected.

    Atomicity: `SELECT ... FOR UPDATE` row-locks the target order before
    reading its existing transactions. A second, concurrent create() for the
    same order blocks on that lock until the first's transaction commits (or
    rolls back), then re-reads with the first's write now visible — so two
    simultaneous requests can never both observe "no chargeable transaction
    yet" and both proceed to create one. This is the standard Odoo/Postgres
    pattern for exactly this class of race (the same technique Odoo core uses
    for stock reservations and sequence claims), not a process-local lock or
    a non-atomic check-then-insert.
    """

    _inherit = "payment.transaction"

    @api.model_create_multi
    def create(self, vals_list):
        guarded_vals = []
        passthrough_vals = []
        for vals in vals_list:
            order_id = self._kartatap_guarded_order_id(vals)
            if order_id:
                guarded_vals.append((vals, order_id))
            else:
                passthrough_vals.append(vals)

        # Records for non-KartaTap orders (or transactions not linked to any
        # sale.order at all) go through Odoo's normal, unmodified create().
        created = super().create(passthrough_vals) if passthrough_vals else self.browse()

        for vals, order_id in guarded_vals:
            resolved = self._create_or_reuse_for_order(vals, order_id)
            created |= resolved

        return created

    @api.model
    def _kartatap_guarded_order_id(self, vals):
        """Return the single sale.order id this transaction targets, if that
        order is KartaTap-originated — else None (unguarded, normal flow)."""
        order_ids = self._extract_x2many_ids(vals.get("sale_order_ids"))
        if len(order_ids) != 1:
            # Zero or multiple orders per transaction is not the KartaTap
            # checkout shape (it always links exactly one) — leave it to
            # Odoo's normal behavior rather than guessing which order to lock.
            return None
        order = self.env["sale.order"].sudo().browse(order_ids[0])
        if not order.exists() or not order.kartatap_request_id:
            return None
        return order.id

    @staticmethod
    def _extract_x2many_ids(command):
        """Best-effort extraction of target ids from an x2many write/create
        command list, e.g. [(6, 0, [3])] or [(4, 3)] or a bare [3]."""
        if not command:
            return []
        ids = []
        for item in command:
            if isinstance(item, int):
                ids.append(item)
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                if item[0] == 6 and len(item) >= 3:
                    ids.extend(item[2])
                elif item[0] in (4, 1):
                    ids.append(item[1])
        return ids

    def _create_or_reuse_for_order(self, vals, order_id):
        # Row-lock: held until this DB transaction (this create() call's
        # enclosing request) commits or rolls back. A concurrent second
        # caller targeting the same order_id blocks here until then.
        self.env.cr.execute(
            "SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (order_id,)
        )

        existing = self.sudo().search(
            [("sale_order_ids", "in", [order_id]), ("state", "in", CHARGEABLE_STATES)],
            order="id desc",
        )
        done_or_authorized = existing.filtered(lambda t: t.state in ("done", "authorized"))
        if done_or_authorized:
            raise ValidationError(
                "This order already has %s payment (transaction %s, state=%s). "
                "A second chargeable transaction cannot be created against an "
                "order that is already paid or authorized."
                % (
                    "an authorized" if done_or_authorized[0].state == "authorized" else "a completed",
                    done_or_authorized[0].reference,
                    done_or_authorized[0].state,
                )
            )

        pending = existing.filtered(lambda t: t.state == "pending")
        if pending:
            _logger.info(
                "kartatap duplicate-payment guard: reusing pending transaction %s "
                "for order %s instead of creating a new one",
                pending[0].reference, order_id,
            )
            return pending[0]

        # No chargeable transaction exists (none at all, or only
        # failed/canceled/draft ones) — a fresh attempt is safe.
        return super(PaymentTransaction, self).create([vals])

    # ------------------------------------------------------------------
    # A transaction is created in 'draft' — NOT yet chargeable — so the
    # create() guard above cannot be the only enforcement point: two
    # transactions for the same order can both be created in 'draft' before
    # either progresses, and would then race to become chargeable
    # independently. Odoo's own state machine funnels every path to a
    # chargeable state through exactly these three methods (_set_pending,
    # _set_authorized, _set_done — used uniformly by every payment provider
    # integration including Stripe's webhook/redirect handlers), so guarding
    # them here closes that window with the same row-lock discipline.

    def _set_pending(self, state_message=None):
        self._kartatap_guard_transition("pending")
        return super()._set_pending(state_message=state_message)

    def _set_authorized(self, state_message=None):
        self._kartatap_guard_transition("authorized")
        return super()._set_authorized(state_message=state_message)

    def _set_done(self, state_message=None):
        self._kartatap_guard_transition("done")
        return super()._set_done(state_message=state_message)

    def _kartatap_guard_transition(self, target_state):
        for tx in self:
            orders = tx.sale_order_ids.filtered(lambda o: o.kartatap_request_id)
            if len(orders) != 1:
                continue
            order = orders[0]
            self.env.cr.execute(
                "SELECT id FROM sale_order WHERE id = %s FOR UPDATE", (order.id,)
            )
            other_chargeable = self.env["payment.transaction"].sudo().search([
                ("sale_order_ids", "in", [order.id]),
                ("state", "in", CHARGEABLE_STATES),
                ("id", "!=", tx.id),
            ])
            if other_chargeable:
                raise ValidationError(
                    "Order %s already has a chargeable transaction (%s, state=%s). "
                    "Transaction %s cannot transition to '%s' — this is the "
                    "concurrent-request case of the F7 duplicate-payment guard: "
                    "two transactions raced to become chargeable for the same "
                    "order, and only the first one through the lock wins."
                    % (order.id, other_chargeable[0].reference, other_chargeable[0].state,
                       tx.reference, target_state)
                )
