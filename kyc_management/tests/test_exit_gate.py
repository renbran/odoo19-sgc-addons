# -*- coding: utf-8 -*-
"""Wave 4 closure pass: TestExitGate for kyc_management.

The Wave 3 protocol's §6.4 "exactly 7 test methods on TestExitGate"
assertion was specific to ``sgc_process_control``'s fail-closed mixin.
For the Wave 4 modules the protocol's count is replaced by a
module-specific expected-count manifest
(see ``docs/WAVE_4_INSTALL_REGRESSION_RESULT.md`` §10.1). For
``kyc_management`` the §6.4 gate is ``TestExitGate`` and the
expected ``testsRun`` is ≥ 5, covering at minimum:

  1. Authorized officer routing succeeds (a user in
     ``group_kyc_approver`` receives a ``kyc.approval`` record).
  2. Unrelated users receive no approval record.
  3. Empty / misconfigured officer group fails safely (no approval
     created, no exception raised).
  4. Duplicate ``kyc_id`` remains blocked after a fresh create.
  5. Inactive users in the approver group are excluded from routing.

The class is intentionally registered under the ``/kyc_management``
selector for §6.2 *and* the §6.4 ``:TestExitGate`` selector, so a
manifest-encoded verifier can enforce the per-scope expected count.
"""

from odoo.tests import TransactionCase


class TestExitGate(TransactionCase):
    """Behavioural gate covering the five must-pass cases for kyc_management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Application = cls.env['kyc.application']
        cls.Approval = cls.env['kyc.approval']
        cls.approver_group = cls.env.ref('kyc_management.group_kyc_approver')
        cls.partner = cls.env['res.partner'].create({
            'name': 'Wave4 ExitGate Applicant',
        })

    def _create_application(self, **overrides):
        vals = {
            'partner_id': self.partner.id,
            'email': 'applicant@example.com',
            'phone': '+971500000000',
            'first_name': 'ExitGate',
        }
        vals.update(overrides)
        return self.Application.create(vals)

    def _make_officer(self, login, active=True):
        """Create a user that belongs to ``group_kyc_approver``.

        ``auth_signup`` raises UserError if we try to create an
        inactive user (the signup reset-password mailer refuses
        archived users), so we always create the user active and
        archive it as a follow-up write when ``active=False`` was
        requested.
        """
        user = self.env['res.users'].create({
            'name': f'Wave4 ExitGate Officer {login}',
            'login': login,
            'email': f'{login}@example.com',
            'group_ids': [
                (4, self.env.ref('base.group_user').id),
                (4, self.approver_group.id),
            ],
        })
        if not active:
            user.write({'active': False})
        return user

    # ------------------------------------------------------------------
    # Case 1 — Authorized officer routing succeeds
    # ------------------------------------------------------------------

    def test_authorized_officer_in_group_gets_approval_record(self):
        """An active user in ``group_kyc_approver`` must receive a
        ``kyc.approval`` record when the application's officer routing
        helper runs. This is the primary gate — without it, KYC
        applications would sit in ``submitted`` with no assigned
        officer."""
        officer = self._make_officer('wave4_eg_officer_1')
        app = self._create_application()
        app._create_approval_and_notify_officer()
        approval = self.Approval.search([
            ('kyc_application_id', '=', app.id),
            ('approver_id', '=', officer.id),
        ])
        self.assertTrue(
            approval,
            "Authorized officer in group_kyc_approver must receive a "
            "kyc.approval record",
        )

    # ------------------------------------------------------------------
    # Case 2 — Unrelated users receive no approval
    # ------------------------------------------------------------------

    def test_unrelated_user_gets_no_approval(self):
        """A user that is not in ``group_kyc_approver`` must never
        receive a ``kyc.approval`` record for someone else's
        application. This is the negative-side companion to case 1."""
        unrelated = self.env['res.users'].create({
            'name': 'Wave4 ExitGate Unrelated',
            'login': 'wave4_eg_unrelated',
            'email': 'wave4_eg_unrelated@example.com',
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        app = self._create_application()
        app._create_approval_and_notify_officer()
        approval = self.Approval.search([
            ('kyc_application_id', '=', app.id),
            ('approver_id', '=', unrelated.id),
        ])
        self.assertFalse(
            approval,
            "Unrelated user must not receive a kyc.approval record",
        )

    # ------------------------------------------------------------------
    # Case 3 — Empty officer group fails safely
    # ------------------------------------------------------------------

    def test_empty_approver_group_creates_no_approval(self):
        """When no active user belongs to ``group_kyc_approver``, the
        officer-routing helper must complete without raising and
        must not create any ``kyc.approval`` records. The application
        remains in ``draft`` until an officer is configured."""
        # Deactivate every existing approver-group user to ensure the
        # group is effectively empty for this test.
        officers = self.env['res.users'].search([
            ('group_ids', 'in', [self.approver_group.id]),
        ])
        officers.write({'active': False})
        try:
            app = self._create_application()
            # Must not raise.
            app._create_approval_and_notify_officer()
            approvals = self.Approval.search([
                ('kyc_application_id', '=', app.id),
            ])
            self.assertEqual(
                len(approvals), 0,
                "Empty approver group must yield zero kyc.approval records",
            )
        finally:
            # Restore officers so subsequent tests aren't poisoned.
            officers.write({'active': True})

    # ------------------------------------------------------------------
    # Case 4 — Duplicate kyc_id remains blocked
    # ------------------------------------------------------------------

    def test_duplicate_kyc_id_blocked_by_constraint(self):
        """Creating a second application with the same ``kyc_id`` must
        be rejected by the migrated ``models.Constraint``. This is the
        re-verification the §6.4 gate exists to lock in."""
        self._create_application(kyc_id='WAVE4_EXIT_GATE_DUP')
        with self.assertRaises(Exception):
            self._create_application(kyc_id='WAVE4_EXIT_GATE_DUP')

    # ------------------------------------------------------------------
    # Case 5 — Inactive officer excluded from routing
    # ------------------------------------------------------------------

    def test_inactive_user_excluded_from_routing(self):
        """An inactive user in ``group_kyc_approver`` must not receive
        a ``kyc.approval`` record — the routing helper filters by
        ``active=True``. An inactive officer cannot act, so they must
        not be assigned."""
        inactive_officer = self._make_officer(
            'wave4_eg_inactive', active=False,
        )
        # Also create an active officer so the helper has someone to
        # route to; the assertion is specifically about the inactive
        # one receiving no approval.
        self._make_officer('wave4_eg_active')
        app = self._create_application()
        app._create_approval_and_notify_officer()
        approval = self.Approval.search([
            ('kyc_application_id', '=', app.id),
            ('approver_id', '=', inactive_officer.id),
        ])
        self.assertFalse(
            approval,
            "Inactive officer must not receive a kyc.approval record",
        )