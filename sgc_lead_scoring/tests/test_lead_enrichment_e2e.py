# -*- coding: utf-8 -*-
"""End-to-end coverage for the AI-enrich button -> wizard -> `_enrich_lead()`
-> structured chatter note flow, rewritten against the Universal JSON
Contract pipeline (Task 8).

The old version mocked legacy `multi_search`/`call_llm` shapes and asserted
on the old free-text 'AI Research Summary' + provider-name-in-body format.
The current chatter format is built by `crm_lead.py::_lead_intelligence_note`
(read directly, not guessed): a `<b>AI Research Summary</b>` header, an
`<p>{executive_summary}</p>` paragraph, `<p><b>{Title}</b></p><ul>...</ul>`
sections for key findings / risks / opportunities / recommended next
actions, a `<p><b>Conversation Strategy</b>: ...</p>` line, and a trailing
`<p><i>Sources: {providers}</i></p>` line.
"""
import json
from unittest.mock import patch

from markupsafe import Markup

from odoo.tests.common import HttpCase, tagged

from odoo.addons.sgc_lead_scoring.models import lead_intelligence as li


def _scores_block(score=80, confidence='high', reason='strong'):
    scores = {}
    for key, _field in li.SCORE_KEYS:
        scores['%s_score' % key] = {'score': score, 'confidence': confidence, 'reason': reason}
    return scores


@tagged('-at_install', 'post_install')
class TestLeadEnrichmentE2E(HttpCase):

    def test_ai_enrich_button_produces_structured_chatter(self):
        lead = self.env['crm.lead'].create({
            'name': 'E2E Test Lead', 'partner_name': 'E2E Acme', 'website': 'https://e2eacme.com',
        })
        # action_enrich_leads() raises UserError without a configured
        # provider (no llm.provider is seeded active+default) -- same gap
        # found in Task 14; create a minimal one for this E2E path too.
        provider = self.env['llm.provider'].create({
            'name': 'E2E Test Provider', 'provider_type': 'openai',
            'model_name': 'gpt-4', 'api_key': 'test-key',
        })
        contract = json.dumps({
            'metadata': {'schema_version': '1.0', 'providers_used': ['tavily']},
            'classification': {'entity_type': 'b2b_company', 'confidence': 'high'},
            'scores': _scores_block(),
            'customer_intelligence': {'industry': {'value': 'Manufacturing'}},
            'buying_intelligence': {'budget_readiness': {'value': 'AED 5M+'}},
            'summary': {
                'executive_summary': 'E2E Acme is a promising test company.',
                'key_findings': ['Growing fast', 'New facility'],
                'conversation_strategy': 'Lead with ROI.',
                'risks': ['Long procurement cycle'],
                'opportunities': ['Digital transformation budget'],
                'recommended_next_actions': ['Book discovery call'],
            },
        })
        with patch(
            'odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search',
            return_value={
                'success': True,
                'results': [{'title': 'E2E Acme', 'url': 'https://e2eacme.com', 'snippet': 'a company', 'sources': ['tavily']}],
                'providers_used': ['tavily'],
                'cache_hits': 0,
                'latency_ms': 90,
            },
        ), patch(
            'odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm',
            return_value={'success': True, 'content': contract, 'error': None, 'retries': 0},
        ):
            wizard = self.env['lead.enrichment.wizard'].create({
                'lead_ids': [(6, 0, lead.ids)], 'provider_id': provider.id, 'parallel': False,
            })
            wizard.action_enrich_leads()

        lead.invalidate_recordset()
        self.assertEqual(lead.ai_enrichment_status, 'completed')
        messages = lead.message_ids.filtered(lambda m: 'AI Research Summary' in (m.body or ''))
        self.assertTrue(messages)
        # `_lead_intelligence_note()` now returns a `markupsafe.Markup`
        # instance (fixed: previously a plain `str`, which `message_post()`
        # HTML-escaped wholesale -- "escape if text, keep if markup", per
        # mail_thread.py -- so the intended bold/bullet-list formatting never
        # rendered). Assert both the visible text content AND that the
        # structural tags survive un-escaped, proving the rendering fix.
        body = messages[0].body
        self.assertIsInstance(body, Markup)
        self.assertIn('<b>AI Research Summary</b>', body)
        self.assertIn('<ul>', body)
        self.assertIn('AI Research Summary', body)
        self.assertIn('E2E Acme is a promising test company.', body)
        self.assertIn('Growing fast', body)
        self.assertIn('Lead with ROI.', body)
        self.assertIn('Long procurement cycle', body)
        self.assertIn('Digital transformation budget', body)
        self.assertIn('Book discovery call', body)
        self.assertIn('Sources', body)
        self.assertIn('tavily', body)
