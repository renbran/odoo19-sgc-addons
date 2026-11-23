# -*- coding: utf-8 -*-
"""Tests for the Lead Intelligence Engine — helper module pure functions
(Task 4 "added tests") and the orchestrator pipeline (`crm.lead._enrich_lead`).

The pure-function coverage mirrors the standalone TDD harness but runs inside
Odoo's runner; the pipeline coverage asserts the max-2-LLM-call contract and
the three terminal statuses against mocked search/LLM services.
"""
import json
import types
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from odoo.addons.sgc_lead_scoring.models import lead_intelligence as li


def _fake_lead(**kw):
    """Duck-typed crm.lead for classify_entity_hint (reads attributes only)."""
    defaults = dict(partner_id=None, email_from='', partner_name='',
                    contact_name='', website='', name='')
    defaults.update(kw)
    return types.SimpleNamespace(**defaults)


def _fake_partner(company_type):
    ns = types.SimpleNamespace(company_type=company_type)
    return ns


class TestLeadIntelligenceHelpers(TransactionCase):
    """Pure functions in lead_intelligence.py (Decisions A, E, G, G.1, H, I)."""

    # ---- entity_family (Decision I) -------------------------------------
    def test_entity_family_b2b_members(self):
        for et in ('b2b_company', 'sme', 'enterprise', 'government', 'non_profit',
                   'investor', 'vendor', 'supplier', 'partner', 'recruit'):
            self.assertEqual(li.entity_family(et), 'b2b', et)

    def test_entity_family_b2c(self):
        self.assertEqual(li.entity_family('b2c_individual'), 'b2c')

    def test_entity_family_unknown(self):
        self.assertEqual(li.entity_family('unknown'), '')
        self.assertEqual(li.entity_family('garbage'), '')
        self.assertEqual(li.entity_family(None), '')

    # ---- compute_readiness_label (Decision G.1) -------------------------
    def _lbl(self, win, need=0, budget=0):
        return li.compute_readiness_label({
            'ai_win_probability_score': win,
            'ai_need_score': need,
            'ai_budget_score': budget,
        })

    def test_readiness_hot(self):
        self.assertEqual(self._lbl(80, 75), 'Hot')
        self.assertEqual(self._lbl(75, 70), 'Hot')

    def test_readiness_warm(self):
        self.assertEqual(self._lbl(80, 60), 'Warm')
        self.assertEqual(self._lbl(65, 50, 70), 'Warm')
        self.assertEqual(self._lbl(60, 60), 'Warm')

    def test_readiness_nurture(self):
        self.assertEqual(self._lbl(65, 50, 50), 'Nurture')
        self.assertEqual(self._lbl(45, 90, 90), 'Nurture')
        self.assertEqual(self._lbl(40), 'Nurture')

    def test_readiness_cold(self):
        self.assertEqual(self._lbl(30, 90, 90), 'Cold')
        self.assertEqual(self._lbl(39.9), 'Cold')
        self.assertEqual(li.compute_readiness_label({}), 'Cold')

    # ---- format_scoring_rationale (Decision H) --------------------------
    def test_rationale_exactly_11_lines(self):
        self.assertEqual(len(li.format_scoring_rationale({}).splitlines()), 11)
        self.assertEqual(len(li.format_scoring_rationale(None).splitlines()), 11)

    def test_rationale_order_and_labels(self):
        lines = li.format_scoring_rationale({}).splitlines()
        self.assertTrue(lines[0].startswith('Need ('))
        self.assertTrue(lines[6].startswith('Digital Maturity ('))
        self.assertTrue(lines[7].startswith('Implementation Complexity ('))
        self.assertTrue(lines[10].startswith('Opportunity ('))

    def test_rationale_populated_line(self):
        out = li.format_scoring_rationale({
            'need_score': {'score': 82, 'confidence': 'high', 'reason': 'Active inquiry.'},
        })
        self.assertEqual(out.splitlines()[0], 'Need (82, High): Active inquiry.')

    def test_rationale_missing_reason_placeholder(self):
        out = li.format_scoring_rationale({
            'budget_score': {'score': 45, 'confidence': 'medium'},
        })
        self.assertEqual(out.splitlines()[1],
                         'Budget (45, Medium): no reason provided by source')

    # ---- normalize_evidence ---------------------------------------------
    def test_normalize_evidence_maps_fields(self):
        ev = li.normalize_evidence({'results': [
            {'title': 'T', 'url': 'U', 'snippet': 'S', '_provider': 'tavily', 'sources': ['tavily']},
        ]})
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]['provider'], 'tavily')
        self.assertEqual(ev[0]['title'], 'T')
        self.assertIn('retrieved_at', ev[0])

    def test_normalize_evidence_provider_from_sources(self):
        ev = li.normalize_evidence({'results': [
            {'title': 'T', 'url': 'U', 'snippet': 'S', 'sources': ['exa']}]})
        self.assertEqual(ev[0]['provider'], 'exa')

    def test_normalize_evidence_empty(self):
        self.assertEqual(li.normalize_evidence({'results': []}), [])
        self.assertEqual(li.normalize_evidence({}), [])
        self.assertEqual(li.normalize_evidence(None), [])

    def test_normalize_evidence_caps_item_count(self):
        """Context-bloat guardrail: more hits than MAX_EVIDENCE_ITEMS are dropped."""
        results = [{'title': 'T%d' % i, 'url': 'U%d' % i, 'snippet': 'S'}
                   for i in range(li.MAX_EVIDENCE_ITEMS + 5)]
        ev = li.normalize_evidence({'results': results})
        self.assertEqual(len(ev), li.MAX_EVIDENCE_ITEMS)
        self.assertEqual(ev[0]['title'], 'T0')

    def test_normalize_evidence_truncates_snippet(self):
        """Context-bloat guardrail: an oversized snippet is truncated."""
        long_snippet = 'x' * (li.MAX_SNIPPET_CHARS + 200)
        ev = li.normalize_evidence({'results': [
            {'title': 'T', 'url': 'U', 'snippet': long_snippet}]})
        self.assertEqual(len(ev[0]['snippet']), li.MAX_SNIPPET_CHARS)

    # ---- apply_evidence_guardrails (hallucination guard) -----------------
    def test_guardrail_no_evidence_forces_low_confidence(self):
        parsed = {'classification': {'entity_type': 'b2b_company', 'confidence': 'high'}}
        out = li.apply_evidence_guardrails(parsed, [])
        self.assertEqual(out['classification']['confidence'], 'low')

    def test_guardrail_no_evidence_drops_all_sources(self):
        parsed = {'classification': {'confidence': 'high'},
                  'sources': [{'url': 'https://invented.example', 'title': 'made up'}]}
        out = li.apply_evidence_guardrails(parsed, [])
        self.assertEqual(out['sources'], [])

    def test_guardrail_with_evidence_keeps_confidence(self):
        parsed = {'classification': {'entity_type': 'b2b_company', 'confidence': 'high'}}
        evidence = [{'url': 'https://real.example', 'title': 'T', 'snippet': 'S'}]
        out = li.apply_evidence_guardrails(parsed, evidence)
        self.assertEqual(out['classification']['confidence'], 'high')

    def test_guardrail_drops_ungrounded_citation(self):
        """A source URL the model was never shown is a fabricated citation."""
        parsed = {'classification': {'confidence': 'high'},
                  'sources': [
                      {'url': 'https://real.example', 'title': 'real hit'},
                      {'url': 'https://invented.example', 'title': 'never shown to the model'},
                  ]}
        evidence = [{'url': 'https://real.example', 'title': 'real hit', 'snippet': 'S'}]
        out = li.apply_evidence_guardrails(parsed, evidence)
        self.assertEqual([s['url'] for s in out['sources']], ['https://real.example'])

    # ---- parse_llm_response (Decision E) --------------------------------
    def _minimal(self):
        return json.dumps({'metadata': {'schema_version': '1.0'},
                           'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'}})

    def test_parse_minimal_valid(self):
        d = li.parse_llm_response(self._minimal())
        self.assertEqual(d['classification']['entity_type'], 'b2c_individual')

    def test_parse_non_json_raises(self):
        with self.assertRaises(li.ParseFailure):
            li.parse_llm_response('summary, not json')

    def test_parse_empty_raises(self):
        with self.assertRaises(li.ParseFailure):
            li.parse_llm_response('')

    def test_parse_missing_metadata_raises(self):
        with self.assertRaises(li.ParseFailure):
            li.parse_llm_response(json.dumps({'classification': {'entity_type': 'x', 'confidence': 'low'}}))

    def test_parse_missing_classification_raises(self):
        with self.assertRaises(li.ParseFailure):
            li.parse_llm_response(json.dumps({'metadata': {'schema_version': '1.0'}}))

    def test_parse_flattens_array_of_objects(self):
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': {'key_findings': [
                {'value': 'Finding one'}, {'text': 'Finding two'}, 'Finding three',
                {'nothing': 'usable'},
            ]},
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['summary']['key_findings'], ['Finding one', 'Finding two', 'Finding three'])

    def test_parse_preserves_sources_objects(self):
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'sources': [{'provider': 'tavily', 'url': 'u', 'confidence': 'high', 'field': 'x'}],
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['sources'][0]['provider'], 'tavily')

    def test_parse_fenced_json(self):
        d = li.parse_llm_response('```json\n' + self._minimal() + '\n```')
        self.assertEqual(d['classification']['confidence'], 'high')

    # ---- _normalize_object_sections (Task 10.5 — schema-object sections
    #      returned as some other JSON type must not crash downstream) -----
    def test_parse_string_shaped_summary_wrapped_as_value(self):
        """The exact live-discovered shape: `summary` as a plain string
        instead of the documented object. Must not raise, and the string
        content must be preserved (not silently dropped) under a generic
        'value' key so downstream consumers can still surface it."""
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': 'Lead is an individual; insufficient evidence to assess intent.',
        })
        d = li.parse_llm_response(payload)
        self.assertIsInstance(d['summary'], dict)
        self.assertEqual(
            d['summary']['value'],
            'Lead is an individual; insufficient evidence to assess intent.')

    def test_parse_list_shaped_summary_treated_as_absent(self):
        """A list has no single salvageable string -> normalized to {}
        (absent), not left as a list that would crash a `.get()` caller."""
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': ['Growing fast', 'New facility'],
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['summary'], {})

    def test_parse_null_shaped_summary_treated_as_absent(self):
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': None,
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['summary'], {})

    def test_parse_boolean_shaped_summary_treated_as_absent(self):
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': True,
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['summary'], {})

    def test_parse_string_shaped_other_object_section_also_normalized(self):
        """The general fix protects EVERY schema-'object' section, not just
        'summary' -- e.g. `customer_intelligence` returned as a bare string."""
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'customer_intelligence': 'Individual buyer, no company.',
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['customer_intelligence'], {'value': 'Individual buyer, no company.'})

    def test_parse_well_formed_summary_object_unaffected(self):
        """A correctly-shaped `summary` object passes through untouched."""
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'summary': {'executive_summary': 'Fine as-is.'},
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['summary'], {'executive_summary': 'Fine as-is.'})

    def test_parse_keeps_scalar_wrapper(self):
        payload = json.dumps({
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'customer_intelligence': {'industry': {'value': 'Real Estate', 'confidence': 'high'}},
        })
        d = li.parse_llm_response(payload)
        self.assertEqual(d['customer_intelligence']['industry']['value'], 'Real Estate')

    # ---- promote_to_native_fields (Decision G) --------------------------
    def _full_parsed(self):
        scores = {}
        for key, _f in li.SCORE_KEYS:
            scores['%s_score' % key] = {'score': 82, 'confidence': 'high', 'reason': 'r'}
        return {
            'metadata': {'schema_version': '1.0'},
            'classification': {'entity_type': 'b2c_individual', 'confidence': 'high'},
            'scores': scores,
            'buying_intelligence': {'budget_readiness': {'value': 'AED 1-2M'}},
            'customer_intelligence': {'industry': {'value': 'Real Estate'}},
            'future_unknown_section': {'x': 1},
        }

    def test_promote_keys_present(self):
        out = li.promote_to_native_fields(self._full_parsed())
        expected = {f for _k, f in li.SCORE_KEYS} | {
            'ai_entity_type', 'ai_entity_type_confidence', 'ai_scoring_rationale',
            'ai_budget_tier', 'ai_industry', 'ai_readiness', 'ai_classification_mismatch',
        }
        self.assertTrue(expected.issubset(set(out)))

    def test_promote_scores_floats_and_clamped(self):
        f = self._full_parsed()
        f['scores']['need_score']['score'] = 150
        f['scores']['budget_score']['score'] = -20
        out = li.promote_to_native_fields(f)
        self.assertEqual(out['ai_need_score'], 100.0)
        self.assertEqual(out['ai_budget_score'], 0.0)
        self.assertIsInstance(out['ai_authority_score'], float)

    def test_promote_entity_type_and_confidence(self):
        out = li.promote_to_native_fields(self._full_parsed())
        self.assertEqual(out['ai_entity_type'], 'b2c_individual')
        self.assertEqual(out['ai_entity_type_confidence'], 'high')

    def test_promote_unknown_entity_type_defaults(self):
        f = self._full_parsed()
        f['classification']['entity_type'] = 'martian'
        self.assertEqual(li.promote_to_native_fields(f)['ai_entity_type'], 'unknown')

    def test_promote_industry_and_budget(self):
        out = li.promote_to_native_fields(self._full_parsed())
        self.assertEqual(out['ai_industry'], 'Real Estate')
        self.assertEqual(out['ai_budget_tier'], 'AED 1-2M')

    def test_promote_industry_fallback_company(self):
        f = self._full_parsed()
        del f['customer_intelligence']
        f['company_intelligence'] = {'industry': {'value': 'Manufacturing'}}
        self.assertEqual(li.promote_to_native_fields(f)['ai_industry'], 'Manufacturing')

    def test_promote_budget_default_unknown(self):
        f = self._full_parsed()
        del f['buying_intelligence']
        self.assertEqual(li.promote_to_native_fields(f)['ai_budget_tier'], 'Unknown')

    def test_promote_rationale_11_lines(self):
        out = li.promote_to_native_fields(self._full_parsed())
        self.assertEqual(len(out['ai_scoring_rationale'].splitlines()), 11)

    def test_promote_readiness(self):
        self.assertEqual(li.promote_to_native_fields(self._full_parsed())['ai_readiness'], 'Hot')

    def test_promote_missing_scores_default_zero(self):
        out = li.promote_to_native_fields({
            'metadata': {}, 'classification': {'entity_type': 'unknown', 'confidence': 'low'}})
        self.assertEqual(out['ai_need_score'], 0.0)

    # ---- classify_entity_hint matrix (Decision A) -----------------------
    def test_classify_rule1_partner_company(self):
        lead = _fake_lead(partner_id=_fake_partner('company'))
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'b2b_company')

    def test_classify_rule2_corporate_email_no_contact(self):
        lead = _fake_lead(email_from='sales@acme.com', contact_name='')
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'b2b_company')

    def test_classify_rule3_public_email_no_company_no_site(self):
        lead = _fake_lead(email_from='jane@gmail.com')
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'b2c_individual')

    def test_classify_rule4_company_no_public_email_with_site(self):
        lead = _fake_lead(partner_name='Acme', website='acme.com')
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'b2b_company')

    def test_classify_public_email_with_company_unknown(self):
        lead = _fake_lead(partner_name='Acme', email_from='x@gmail.com', website='acme.com')
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'unknown')

    def test_classify_corporate_email_with_contact_unknown(self):
        lead = _fake_lead(email_from='john@acme.com', contact_name='John')
        self.assertEqual(li.classify_entity_hint(lead, self.env), 'unknown')

    def test_classify_all_empty_unknown(self):
        self.assertEqual(li.classify_entity_hint(_fake_lead(), self.env), 'unknown')

    def test_classify_always_returns_one_of_three(self):
        for lead in (_fake_lead(partner_id=_fake_partner('company')),
                     _fake_lead(email_from='jane@gmail.com'),
                     _fake_lead()):
            self.assertIn(li.classify_entity_hint(lead, self.env),
                          ('b2b_company', 'b2c_individual', 'unknown'))

    def test_classify_on_real_leads(self):
        company = self.env['res.partner'].create({'name': 'RealCo', 'company_type': 'company'})
        lead_b2b = self.env['crm.lead'].create({'name': 'RealCo Deal', 'partner_id': company.id})
        self.assertEqual(li.classify_entity_hint(lead_b2b, self.env), 'b2b_company')
        lead_b2c = self.env['crm.lead'].create({'name': 'Jane Buyer', 'email_from': 'jane@gmail.com'})
        self.assertEqual(li.classify_entity_hint(lead_b2c, self.env), 'b2c_individual')


class TestLeadIntelligencePipeline(TransactionCase):
    """`crm.lead._enrich_lead` orchestrator (Decisions B — max 2 calls)."""

    def setUp(self):
        super().setUp()
        self.lead = self.env['crm.lead'].create({
            'name': 'Acme Corp Deal',
            'partner_name': 'Acme Corp',
            'website': 'https://acme.com',
        })

    def _multi_search(self, *_a, **_k):
        return {
            'success': True,
            'results': [{'title': 'Acme', 'url': 'https://acme.com', 'snippet': 'x',
                         '_provider': 'tavily', 'sources': ['tavily']}],
            'providers_used': ['tavily'],
            'cache_hits': 0,
            'latency_ms': 120,
        }

    def _good_contract(self):
        scores = {}
        for key, _f in li.SCORE_KEYS:
            scores['%s_score' % key] = {'score': 80, 'confidence': 'high', 'reason': 'strong'}
        return json.dumps({
            'metadata': {'schema_version': '1.0', 'providers_used': ['tavily']},
            'classification': {'entity_type': 'b2b_company', 'confidence': 'high'},
            'scores': scores,
            'customer_intelligence': {'industry': {'value': 'Manufacturing'}},
            'buying_intelligence': {'budget_readiness': {'value': 'AED 5M+'}},
            'summary': {
                'executive_summary': 'Acme is a promising manufacturer.',
                'key_findings': ['Growing fast', 'New facility'],
                'conversation_strategy': 'Lead with ROI.',
                'risks': ['Long procurement cycle'],
                'opportunities': ['Digital transformation budget'],
                'recommended_next_actions': ['Book discovery call'],
            },
        })

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_completed_single_call(self, mock_search, mock_llm):
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        self.lead._enrich_lead()
        self.assertEqual(mock_llm.call_count, 1)
        self.assertEqual(self.lead.ai_enrichment_status, 'completed')
        self.assertEqual(self.lead.ai_need_score, 80.0)
        self.assertEqual(self.lead.ai_entity_type, 'b2b_company')
        self.assertEqual(self.lead.ai_entity_type_confidence, 'high')
        self.assertEqual(self.lead.ai_industry, 'Manufacturing')
        self.assertEqual(self.lead.ai_budget_tier, 'AED 5M+')
        self.assertEqual(self.lead.ai_readiness, 'hot')
        self.assertEqual(len(self.lead.ai_scoring_rationale.splitlines()), 11)
        # artifact 3 (normalized evidence) persisted
        evidence = json.loads(self.lead.ai_enrichment_evidence)
        self.assertEqual(evidence[0]['provider'], 'tavily')
        # artifact 2 (full JSON) persisted
        self.assertEqual(json.loads(self.lead.ai_enrichment_data)['classification']['entity_type'],
                         'b2b_company')
        self.assertTrue(self.lead.ai_last_enrichment_date)
        note = self.lead.message_ids.filtered(lambda m: 'AI Research Summary' in (m.body or ''))
        self.assertTrue(note)
        self.assertIn('tavily', note[0].body)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_retry_once_then_success(self, mock_search, mock_llm):
        mock_search.side_effect = self._multi_search
        mock_llm.side_effect = [
            {'success': True, 'content': 'not json at all', 'error': '', 'retries': 0},
            {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0},
        ]
        self.lead._enrich_lead()
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(self.lead.ai_enrichment_status, 'completed')

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_terminal_parse_failure(self, mock_search, mock_llm):
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': 'still not json', 'error': '', 'retries': 0}
        self.lead._enrich_lead()
        self.assertEqual(mock_llm.call_count, 2)
        self.assertEqual(self.lead.ai_enrichment_status, 'parse_failure')
        # raw content persisted for diagnosis
        self.assertEqual(self.lead.ai_enrichment_data, 'still not json')
        note = self.lead.message_ids.filtered(lambda m: 'AI Research Summary' in (m.body or ''))
        self.assertTrue(note)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_processing_guard_early_return(self, mock_search, mock_llm):
        self.lead.ai_enrichment_status = 'processing'
        self.lead._enrich_lead()
        mock_search.assert_not_called()
        mock_llm.assert_not_called()

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_entity_hint_persisted(self, mock_search, mock_llm):
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        self.lead._enrich_lead()
        # partner_name + website, no public email -> b2b_company hint (rule 4)
        self.assertEqual(self.lead.entity_hint, 'b2b_company')
        # hint b2b, llm b2b, high conf -> no mismatch
        self.assertFalse(self.lead.ai_classification_mismatch)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_classification_mismatch_flagged(self, mock_search, mock_llm):
        mock_search.side_effect = self._multi_search
        contract = json.loads(self._good_contract())
        contract['classification'] = {'entity_type': 'b2c_individual', 'confidence': 'high'}
        mock_llm.return_value = {'success': True, 'content': json.dumps(contract), 'error': '', 'retries': 0}
        self.lead._enrich_lead()
        # hint b2b (rule 4) vs llm b2c at high confidence -> mismatch
        self.assertEqual(self.lead.entity_hint, 'b2b_company')
        self.assertEqual(self.lead.ai_entity_type, 'b2c_individual')
        self.assertTrue(self.lead.ai_classification_mismatch)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_contact_name_anonymized_in_prompt(self, mock_search, mock_llm):
        self.env['ir.config_parameter'].sudo().set_param(
            'llm_lead_scoring.anonymize_customer_names', 'True')
        b2c = self.env['crm.lead'].create({
            'name': 'Jane Deal', 'contact_name': 'Jane VerySecret', 'email_from': 'jane@gmail.com'})
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        b2c._enrich_lead()
        sent = mock_llm.call_args.kwargs.get('messages') or mock_llm.call_args[0][0]
        self.assertNotIn('Jane VerySecret', json.dumps(sent))

    # ---- F.2: lead.name / partner_name anonymization, both legs ---------

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_lead_name_and_company_name_anonymized_toggle_on(self, mock_search, mock_llm):
        """When the toggle is on, ALL THREE name fields (contact_name, lead
        name, partner_name) must be hashed before reaching both the LLM
        prompt AND the search query (Decision F.2)."""
        self.env['ir.config_parameter'].sudo().set_param(
            'llm_lead_scoring.anonymize_customer_names', 'True')
        lead = self.env['crm.lead'].create({
            'name': 'JaneSecretLeadTitle',
            'contact_name': 'JaneSecretContact',
            'partner_name': 'JaneSecretCompany',
            'website': 'https://acme-secret.example.com',
        })
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        lead._enrich_lead()

        sent = mock_llm.call_args.kwargs.get('messages') or mock_llm.call_args[0][0]
        prompt_text = json.dumps(sent)
        self.assertNotIn('JaneSecretLeadTitle', prompt_text)
        self.assertNotIn('JaneSecretContact', prompt_text)
        self.assertNotIn('JaneSecretCompany', prompt_text)

        queries = mock_search.call_args[0][0]
        query_text = json.dumps(queries)
        self.assertNotIn('JaneSecretLeadTitle', query_text)
        self.assertNotIn('JaneSecretContact', query_text)
        self.assertNotIn('JaneSecretCompany', query_text)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_names_cleartext_when_toggle_off(self, mock_search, mock_llm):
        """Regression: with the toggle OFF (the default), all three name
        fields still reach the prompt in cleartext, and the search query
        subject (company_name, which wins the fallback chain) is also
        cleartext."""
        lead = self.env['crm.lead'].create({
            'name': 'JanePlainLeadTitle',
            'contact_name': 'JanePlainContact',
            'partner_name': 'JanePlainCompany',
            'website': 'https://acme-plain.example.com',
        })
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        lead._enrich_lead()

        sent = mock_llm.call_args.kwargs.get('messages') or mock_llm.call_args[0][0]
        prompt_text = json.dumps(sent)
        self.assertIn('JanePlainLeadTitle', prompt_text)
        self.assertIn('JanePlainContact', prompt_text)
        self.assertIn('JanePlainCompany', prompt_text)

        queries = mock_search.call_args[0][0]
        query_text = json.dumps(queries)
        self.assertIn('JanePlainCompany', query_text)

    @patch('odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm')
    @patch('odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search')
    def test_lead_name_fallback_subject_anonymized_in_query(self, mock_search, mock_llm):
        """The search-query fallback subject (used when partner_name and
        contact_name are both blank) is the anonymized lead name, not the
        raw ``crm.lead.name`` — closing the exact B2C leak Decision F.2
        exists to prevent."""
        self.env['ir.config_parameter'].sudo().set_param(
            'llm_lead_scoring.anonymize_customer_names', 'True')
        lead = self.env['crm.lead'].create({'name': 'JaneOnlyLeadTitleSecret'})
        mock_search.side_effect = self._multi_search
        mock_llm.return_value = {'success': True, 'content': self._good_contract(), 'error': '', 'retries': 0}
        lead._enrich_lead()
        queries = mock_search.call_args[0][0]
        self.assertNotIn('JaneOnlyLeadTitleSecret', json.dumps(queries))
