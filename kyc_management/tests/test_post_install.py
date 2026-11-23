# -*- coding: utf-8 -*-
"""Wave 4 closure pass: post-install tests for kyc_management.

Tagged ``post_install`` so they are intended to run under §6.3
(``--test-tags 'post_install/kyc_management'``).

NOTE on selection semantics: in Odoo 19, an explicit selector like
``/kyc_management`` matches ANY class carrying the ``kyc_management``
tag, regardless of whether the class is also tagged ``post_install``
or excluded with ``-at_install``. The ``-at_install`` exclusion is
honoured only when no explicit include selector is given. As a
result, this class is also selected by §6.2's ``/kyc_management``
selector; that is an artefact of the runtime, not a defect in the
test design.

The tests deliberately avoid ``button_immediate_upgrade()`` and other
module-mutation calls -- those are forbidden inside Odoo's
transactional test harness ("Module operations inside tests are not
transactional and thus forbidden").
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'kyc_management')
class TestPostInstall(TransactionCase):
    """Re-install / upgrade idempotency gate."""

    def test_module_is_installed_after_upgrade_path(self):
        """The module must be in state ``installed`` by the time
        post-install tests run."""
        module = self.env['ir.module.module'].search([
            ('name', '=', 'kyc_management'),
        ])
        self.assertTrue(module, "kyc_management module must be installed")
        self.assertEqual(module.state, 'installed')

    def test_kyc_id_constraint_survives_prior_module_upgrade(self):
        """The migrated ``models.Constraint('UNIQUE(kyc_id)')`` on
        ``kyc.application`` must still be present."""
        Application = self.env['kyc.application']
        partner = self.env['res.partner'].create({
            'name': 'Wave4 PostInstall Applicant',
        })
        base_vals = {
            'partner_id': partner.id,
            'email': 'pi@example.com',
            'phone': '+971500000000',
            'first_name': 'PostInstall',
        }
        Application.create({**base_vals, 'kyc_id': 'WAVE4_PI_DUP'})
        with self.assertRaises(Exception):
            Application.create({**base_vals, 'kyc_id': 'WAVE4_PI_DUP'})