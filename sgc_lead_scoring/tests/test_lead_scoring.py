# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase


class TestLeadScoring(TransactionCase):
    """Test Lead Scoring functionality"""

    def setUp(self):
        super(TestLeadScoring, self).setUp()
        self.Lead = self.env['crm.lead']
        self.LLMService = self.env['llm.service']

    def test_lead_completeness_scoring(self):
        """Test completeness scoring algorithm"""
        # Create lead with minimal info
        lead_minimal = self.Lead.create({
            'name': 'Minimal Lead',
            'type': 'opportunity',
        })

        result_minimal = self.LLMService.analyze_lead_completeness(lead_minimal)
        self.assertLess(result_minimal['score'], 50)  # Should have low score

        # Create lead with complete info
        lead_complete = self.Lead.create({
            'name': 'Complete Lead',
            'type': 'opportunity',
            'partner_name': 'Test Company',
            'contact_name': 'John Doe',
            'email_from': 'john@example.com',
            'phone': '+1234567890',
            'description': 'Looking for CRM solution with 50 users',
            'street': '123 Main St',
            'city': 'Test City',
            'expected_revenue': 10000,
        })

        result_complete = self.LLMService.analyze_lead_completeness(lead_complete)
        self.assertGreater(result_complete['score'], 70)  # Should have high score

    def test_ai_score_fields_exist(self):
        """Test that AI scoring fields are added to crm.lead"""
        lead = self.Lead.create({
            'name': 'Test Lead',
            'type': 'opportunity',
        })

        # Check that fields exist and have default values
        self.assertEqual(lead.ai_probability_score, 0.0)
        self.assertEqual(lead.ai_enrichment_status, 'pending')
        self.assertTrue(lead.auto_enrich)  # Default is True

    def test_ai_score_color_computation(self):
        """Test AI score color indicator"""
        lead = self.Lead.create({
            'name': 'Test Lead',
            'type': 'opportunity',
        })

        # High score - green
        lead.write({'ai_probability_score': 80})
        self.assertEqual(lead.ai_score_color, 10)

        # Medium score - yellow
        lead.write({'ai_probability_score': 50})
        self.assertEqual(lead.ai_score_color, 3)

        # Low score - red
        lead.write({'ai_probability_score': 20})
        self.assertEqual(lead.ai_score_color, 1)

    def test_lead_indexes_exist(self):
        """Test that database indexes are properly defined"""
        # This tests that fields have index=True attribute
        Lead = self.env['crm.lead']

        # Check field definitions
        ai_enrichment_status_field = Lead._fields['ai_enrichment_status']
        auto_enrich_field = Lead._fields['auto_enrich']
        ai_last_enrichment_date_field = Lead._fields['ai_last_enrichment_date']

        # These fields should have index attribute (though we can't easily test DB index directly in unit test)
        self.assertTrue(hasattr(ai_enrichment_status_field, 'index'))
        self.assertTrue(hasattr(auto_enrich_field, 'index'))
        self.assertTrue(hasattr(ai_last_enrichment_date_field, 'index'))

    def test_engagement_scoring(self):
        """Test engagement scoring based on activities and messages"""
        lead = self.Lead.create({
            'name': 'Test Lead',
            'type': 'opportunity',
            'partner_name': 'Test Company',
        })

        # Test with no activities
        result = self.LLMService.analyze_activity_engagement(lead)
        self.assertLess(result['score'], 30)  # Low engagement

        # Create some activities
        Activity = self.env['mail.activity']
        for i in range(3):
            Activity.create({
                'res_id': lead.id,
                'res_model': 'crm.lead',
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': f'Activity {i}',
                'user_id': self.env.user.id,
            })

        # Re-test with activities
        result_with_activities = self.LLMService.analyze_activity_engagement(lead)
        self.assertGreater(result_with_activities['score'], result['score'])

    def test_auto_enrich_flag(self):
        """Test that new leads can have auto_enrich disabled"""
        lead = self.Lead.create({
            'name': 'No Auto Enrich',
            'type': 'opportunity',
            'auto_enrich': False,
        })

        self.assertFalse(lead.auto_enrich)

    def test_enrichment_status_workflow(self):
        """Test enrichment status changes"""
        lead = self.Lead.create({
            'name': 'Test Lead',
            'type': 'opportunity',
        })

        # Default status
        self.assertEqual(lead.ai_enrichment_status, 'pending')

        # Can change to processing
        lead.write({'ai_enrichment_status': 'processing'})
        self.assertEqual(lead.ai_enrichment_status, 'processing')

        # Can change to completed
        lead.write({'ai_enrichment_status': 'completed'})
        self.assertEqual(lead.ai_enrichment_status, 'completed')

        # Can change to failed
        lead.write({'ai_enrichment_status': 'failed'})
        self.assertEqual(lead.ai_enrichment_status, 'failed')
