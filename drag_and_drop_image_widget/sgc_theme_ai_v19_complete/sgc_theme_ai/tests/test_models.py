# -*- coding: utf-8 -*-
"""
SGC TECH AI — Model Tests

FIX P3: Tests for compute fields and model logic.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged('sgc', 'post_install', '-at_install')
class TestSGCLead(TransactionCase):
    """Tests for the extended crm.lead model."""

    def setUp(self):
        super().setUp()
        self.Lead = self.env['crm.lead']

    def test_package_compute_starter(self):
        """1-15 employees maps to Starter."""
        lead = self.Lead.create({
            'name': 'Test Lead Starter',
            'sgc_employees': 10,
        })
        self.assertEqual(lead.sgc_package, 'starter')

    def test_package_compute_growth(self):
        """16-50 employees maps to Growth."""
        lead = self.Lead.create({
            'name': 'Test Lead Growth',
            'sgc_employees': 30,
        })
        self.assertEqual(lead.sgc_package, 'growth')

    def test_package_compute_enterprise(self):
        """51+ employees maps to Enterprise."""
        lead = self.Lead.create({
            'name': 'Test Lead Enterprise',
            'sgc_employees': 100,
        })
        self.assertEqual(lead.sgc_package, 'enterprise')

    def test_package_compute_fires_programmatically(self):
        """compute fires on creation, not just UI onchange."""
        # This test verifies the FIX Q7 — onchange replaced with compute.
        lead = self.Lead.create({
            'name': 'Programmatic Lead',
            'sgc_employees': 20,
        })
        # Must be set even though no UI onchange was triggered
        self.assertIsNotNone(lead.sgc_package)
        self.assertEqual(lead.sgc_package, 'growth')

    def test_roi_computed_when_industry_set(self):
        """ROI projection computed when industry + cost provided."""
        lead = self.Lead.create({
            'name': 'ROI Test Lead',
            'sgc_industry': 'real_estate',
            'sgc_monthly_cost': 100000.0,
            'sgc_employees': 20,
        })
        self.assertGreater(lead.sgc_roi_projection, 0)
        self.assertGreaterEqual(lead.sgc_roi_projection, 150.0)

    def test_roi_zero_without_industry(self):
        """ROI projection is 0 if no industry/cost set."""
        lead = self.Lead.create({'name': 'No Industry Lead'})
        self.assertEqual(lead.sgc_roi_projection, 0.0)

    def test_no_duplicate_field_definition(self):
        """sgc_roi_projection field exists and is a compute field."""
        field = self.Lead._fields.get('sgc_roi_projection')
        self.assertIsNotNone(field, 'Field must exist on the model')
        self.assertTrue(field.compute, 'Must be a compute field (FIX Q1)')


@tagged('sgc', 'post_install', '-at_install')
class TestWebsiteBootstrap(TransactionCase):
    """Tests for clean-install website bootstrap defaults."""

    def test_default_website_homepage_points_to_sgc_home(self):
        website = self.env.ref('website.default_website')
        self.assertEqual(website.homepage_url, '/home')

    def test_module_does_not_create_extra_websites(self):
        self.assertEqual(self.env['website'].search_count([]), 1)
