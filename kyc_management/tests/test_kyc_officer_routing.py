# -*- coding: utf-8 -*-
"""Wave 4A verification: officer routing on new KYC applications.

Covers two things the Wave 4 protocol explicitly requires for this module:

1. A negative test for the migrated `kyc_id_unique` constraint (was a dead
   `_sql_constraints` entry until this remediation pass; must now actually
   reject a duplicate `kyc_id` at create() time).
2. Officer routing: `_create_approval_and_notify_officer()` must create a
   `kyc.approval` record for every active user in `group_kyc_approver`
   (this is the real access-control gate — it decides who can act on the
   application) and must NOT create one for an unrelated user.

Known gap, not fixed here (see Wave 4 result doc): none of the
`mail.template` records this module's `_notify_*` methods reference
(`email_template_kyc_approval_notification` and 6 others) are defined
anywhere in the module. Every one resolves via
`env.ref(..., raise_if_not_found=False)` to `None` and silently no-ops.
The `kyc.approval` record is the actual notification mechanism that
works; the email layer does not send anything today. These tests verify
the mechanism that is real.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "kyc_management")
class TestKycOfficerRouting(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Application = cls.env["kyc.application"]
        cls.Approval = cls.env["kyc.approval"]
        cls.approver_group = cls.env.ref("kyc_management.group_kyc_approver")
        cls.partner = cls.env["res.partner"].create({"name": "Wave4 Test Applicant"})

        cls.officer = cls.env["res.users"].create({
            "name": "Wave4 KYC Officer",
            "login": "wave4_kyc_officer",
            "email": "wave4_kyc_officer@example.com",
            "group_ids": [
                (4, cls.env.ref("base.group_user").id),
                (4, cls.approver_group.id),
            ],
        })
        cls.unrelated_user = cls.env["res.users"].create({
            "name": "Wave4 Unrelated User",
            "login": "wave4_kyc_unrelated",
            "email": "wave4_kyc_unrelated@example.com",
            "group_ids": [(4, cls.env.ref("base.group_user").id)],
        })

    def _create_application(self, **overrides):
        vals = {
            "partner_id": self.partner.id,
            "email": "applicant@example.com",
            "phone": "+971500000000",
            "first_name": "Test",
        }
        vals.update(overrides)
        return self.Application.create(vals)

    def test_kyc_id_unique_constraint_rejects_duplicate(self):
        """Negative test for the migrated models.Constraint."""
        self._create_application(kyc_id="WAVE4DUP001")
        with self.assertRaises(Exception):
            self._create_application(kyc_id="WAVE4DUP001")

    def test_officer_in_approver_group_gets_routed(self):
        """The officer in group_kyc_approver must get a kyc.approval record
        — this is what actually determines who can act on the
        application, i.e. the real notification/routing mechanism."""
        app = self._create_application()
        app._create_approval_and_notify_officer()
        approval = self.Approval.search([
            ("kyc_application_id", "=", app.id),
            ("approver_id", "=", self.officer.id),
        ])
        self.assertTrue(
            approval,
            "Officer in group_kyc_approver must get a kyc.approval record",
        )

    def test_unrelated_user_is_not_routed(self):
        """A user with no compliance role must never get a kyc.approval
        record for someone else's application."""
        app = self._create_application()
        app._create_approval_and_notify_officer()
        approval = self.Approval.search([
            ("kyc_application_id", "=", app.id),
            ("approver_id", "=", self.unrelated_user.id),
        ])
        self.assertFalse(
            approval,
            "Unrelated user must not be routed a kyc.approval record",
        )
