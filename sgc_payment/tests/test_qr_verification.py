from odoo.tests import TransactionCase


class TestQrVerification(TransactionCase):
    def test_create_verification(self):
        verification = self.env['payment.qr.verification'].create({
            'verification_code': 'TEST123',
            'verification_method': 'manual_entry',
            'verification_status': 'success',
        })
        self.assertTrue(verification)
        self.assertEqual(verification.verification_code, 'TEST123')
        self.assertEqual(verification.verification_status, 'success')
