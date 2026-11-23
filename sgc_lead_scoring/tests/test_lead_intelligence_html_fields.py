# -*- coding: utf-8 -*-
"""Tests for the notebook-tab computed Html fields (Task 7).

These fields parse ``ai_enrichment_data`` / ``ai_enrichment_evidence`` as
JSON and render a simple bullet-list HTML fragment. The core design
principle under test is parser tolerance: a missing, empty or malformed
JSON blob must render a friendly placeholder, never raise.
"""
import json

from odoo.tests.common import TransactionCase


class TestLeadIntelligenceHtmlFields(TransactionCase):

    def setUp(self):
        super().setUp()
        self.lead = self.env['crm.lead'].create({
            'name': 'Acme Corp Deal',
            'partner_name': 'Acme Corp',
        })

    def test_html_fields_handle_absent_enrichment_data(self):
        """No enrichment data at all -> every tab renders, none crash."""
        self.lead.ai_enrichment_data = False
        self.lead.ai_enrichment_evidence = False
        self.assertIn('Not applicable', self.lead.ai_company_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_customer_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_relationship_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_buying_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_opportunity_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_proposal_intelligence_html)
        self.assertIn('Not applicable', self.lead.ai_executive_summary_html)
        self.assertIn('No research evidence', self.lead.ai_evidence_html)

    def test_html_fields_handle_malformed_json(self):
        """Non-JSON garbage in ai_enrichment_data must not raise."""
        self.lead.ai_enrichment_data = '{not valid json[[['
        self.lead.ai_enrichment_evidence = 'also not json'
        try:
            html = self.lead.ai_company_intelligence_html
        except Exception as exc:  # noqa: BLE001 - the point is that nothing raises
            self.fail('Malformed JSON crashed the compute method: %s' % exc)
        self.assertIn('Not applicable', html)
        self.assertIn('No research evidence', self.lead.ai_evidence_html)

    def test_html_fields_handle_not_applicable_section(self):
        """A section explicitly marked not_applicable renders the same
        friendly placeholder as an absent section."""
        self.lead.ai_enrichment_data = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'company_intelligence': {'not_applicable': True},
        })
        self.assertIn('Not applicable', self.lead.ai_company_intelligence_html)

    def test_company_intelligence_html_renders_populated_section(self):
        """A populated section renders a bullet list with the field's value."""
        self.lead.ai_enrichment_data = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2b_company', 'confidence': 'high'},
            'company_intelligence': {
                'industry': {'value': 'Manufacturing', 'confidence': 'high', 'reason': 'website copy'},
                'employee_count': {'value': '250-500'},
                'tags': {'value': ['ERP', 'Odoo']},
            },
        })
        html = self.lead.ai_company_intelligence_html
        self.assertIn('Manufacturing', html)
        self.assertIn('confidence: high', html)
        self.assertIn('250-500', html)
        self.assertIn('ERP', html)
        self.assertIn('<ul>', html)

    def test_executive_summary_html_renders_plain_lists_and_strings(self):
        """The 'summary' section uses plain strings/lists rather than
        {value, confidence} wrappers; the same renderer must still handle it."""
        self.lead.ai_enrichment_data = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2b_company', 'confidence': 'medium'},
            'summary': {
                'executive_summary': 'Strong fit, ready to engage.',
                'key_findings': ['Growing team', 'Active RFP'],
                'risks': ['Budget not confirmed'],
            },
        })
        html = self.lead.ai_executive_summary_html
        self.assertIn('Strong fit', html)
        self.assertIn('Growing team', html)
        self.assertIn('Budget not confirmed', html)

    def test_relationship_tab_combines_two_sections_with_titles(self):
        self.lead.ai_enrichment_data = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2b_company', 'confidence': 'high'},
            'relationship_intelligence': {'history': {'value': 'Existing customer since 2022'}},
            'conversation_intelligence': {'tone': {'value': 'Positive'}},
        })
        html = self.lead.ai_relationship_intelligence_html
        self.assertIn('Existing customer since 2022', html)
        self.assertIn('Positive', html)

    def test_evidence_html_renders_normalized_evidence_list(self):
        self.lead.ai_enrichment_evidence = json.dumps([
            {
                'title': 'Acme Corp Overview',
                'url': 'https://acme.com/about',
                'snippet': 'Acme is a mid-size manufacturer.',
                'provider': 'tavily',
                'retrieved_at': '2026-07-22T00:00:00+00:00',
            },
        ])
        html = self.lead.ai_evidence_html
        self.assertIn('Acme Corp Overview', html)
        self.assertIn('https://acme.com/about', html)
        self.assertIn('tavily', html)

    def test_evidence_html_handles_non_list_json(self):
        """A JSON object (not a list) in ai_enrichment_evidence must not raise."""
        self.lead.ai_enrichment_evidence = json.dumps({'unexpected': 'shape'})
        html = self.lead.ai_evidence_html
        self.assertIn('No research evidence', html)
