# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo import api
from odoo.modules.registry import Registry
from odoo.tests.common import TransactionCase


class _SyncExecutor:
    """Test-only stand-in for ThreadPoolExecutor.

    See sgc_lead_scoring/tests/test_cron_concurrency.py for the full
    investigation: a real ThreadPoolExecutor worker deadlocks against
    TransactionCase's shared class transaction even when the worker's
    cursor is fully independent, because the harness's own locking
    contends with a genuinely concurrent thread. Running each lead's
    worker function sequentially in the test's own thread sidesteps that
    contention while still exercising the real per-lead-cursor/commit
    logic -- it just isn't run concurrently during the test. The
    production code (lead_enrichment_wizard.py) is unaffected; only this
    test mocks the executor.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


class TestLeadEnrichmentWizard(TransactionCase):
    """TransactionCase forbids cr.commit()/cr.rollback() on self.env.cr and
    shares ONE transaction (one REPEATABLE READ snapshot) across every test
    method in this class -- see test_cron_concurrency.py for the full
    investigation. Leads are created via a fresh, separately-committing
    cursor, and every operation that must see them (creating the wizard,
    running its action, reading back results) also goes through a fresh
    cursor rather than self.env, whose snapshot may already be frozen from
    an earlier test method in this class."""

    def setUp(self):
        super().setUp()
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            leads = env['crm.lead'].create([
                {'name': 'Lead A', 'partner_name': 'Acme A'},
                {'name': 'Lead B', 'partner_name': 'Acme B'},
            ])
            self.lead_ids = leads.ids
            # action_enrich_leads() raises UserError without a configured
            # provider (no llm.provider is seeded active+default), unrelated
            # to this task -- create a minimal one and pass it explicitly.
            provider = env['llm.provider'].create({
                'name': 'Test Provider', 'provider_type': 'openai',
                'model_name': 'gpt-4', 'api_key': 'test-key',
            })
            self.provider_id = provider.id
            cr.commit()
        self.addCleanup(self._cleanup_committed_records)

    def _cleanup_committed_records(self):
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            env['crm.lead'].browse(self.lead_ids).unlink()
            env['llm.provider'].browse(self.provider_id).unlink()
            cr.commit()

    def _read_statuses(self):
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            return {lead.id: lead.ai_enrichment_status for lead in env['crm.lead'].browse(self.lead_ids)}

    def test_parallel_defaults_true(self):
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            wizard = env['lead.enrichment.wizard'].create({'lead_ids': [(6, 0, self.lead_ids)]})
            self.assertTrue(wizard.parallel)

    def test_action_enrich_leads_parallel_reaches_terminal_status(self):
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            wizard = env['lead.enrichment.wizard'].create({
                'lead_ids': [(6, 0, self.lead_ids)],
                'provider_id': self.provider_id,
                'parallel': True,
            })
            with patch(
                'odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search',
                return_value={'success': True, 'results': [], 'providers_used': [], 'cache_hits': 0, 'latency_ms': 0},
            ), patch(
                'odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm',
                return_value={'success': True, 'content': 'summary', 'error': None, 'retries': 0},
            ), patch(
                'odoo.addons.sgc_lead_scoring.wizards.lead_enrichment_wizard.ThreadPoolExecutor', _SyncExecutor,
            ):
                wizard.action_enrich_leads()

        statuses = self._read_statuses()
        for lead_id, status in statuses.items():
            self.assertNotEqual(status, 'pending', 'lead %s status=%s' % (lead_id, status))

    def test_action_enrich_leads_sequential_still_works(self):
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            wizard = env['lead.enrichment.wizard'].create({
                'lead_ids': [(6, 0, self.lead_ids)],
                'provider_id': self.provider_id,
                'parallel': False,
            })
            with patch(
                'odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search',
                return_value={'success': True, 'results': [], 'providers_used': [], 'cache_hits': 0, 'latency_ms': 0},
            ), patch(
                'odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm',
                return_value={'success': True, 'content': 'summary', 'error': None, 'retries': 0},
            ):
                result = wizard.action_enrich_leads()
            self.assertEqual(result['params']['type'], 'success')
