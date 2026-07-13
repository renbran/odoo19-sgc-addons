# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tests.common import SavepointCase


class TestSaleAgreement(SavepointCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.commercial_partner = cls.env['res.partner'].create({
            'name': 'Example Customer',
            'company_type': 'company',
        })
        cls.contact_partner = cls.env['res.partner'].create({
            'name': 'Example Contact',
            'parent_id': cls.commercial_partner.id,
            'company_type': 'person',
        })
        cls.agreement_model = cls.env['sale.agreement']

    def test_normalize_partner_id_uses_commercial_partner(self):
        normalized_partner_id = self.agreement_model._normalize_partner_id(self.contact_partner.id)
        self.assertEqual(normalized_partner_id, self.commercial_partner.id)

    def test_detect_file_type_for_pdf(self):
        detected_type = self.agreement_model._detect_file_type(b'%PDF-1.7\nexample')
        self.assertEqual(detected_type, 'pdf')

    def test_validate_upload_accepts_matching_pdf(self):
        detected_type = self.agreement_model._validate_upload(
            'license.pdf',
            b'%PDF-1.7\nexample',
            'License',
        )
        self.assertEqual(detected_type, 'pdf')

    def test_validate_upload_rejects_mismatched_extension(self):
        with self.assertRaises(ValidationError):
            self.agreement_model._validate_upload(
                'license.pdf',
                b'\x89PNG\r\n\x1a\nexample',
                'License',
            )

    def test_validate_upload_rejects_oversized_file(self):
        oversized_pdf = b'%PDF-' + (b'0' * (10 * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            self.agreement_model._validate_upload('license.pdf', oversized_pdf, 'License')
