# -*- coding: utf-8 -*-
import json
from unittest.mock import patch

from odoo import api
from odoo.modules.registry import Registry
from odoo.tests.common import TransactionCase

# Minimal valid Universal JSON Contract response. Since the Lead Intelligence
# Engine landed, `_enrich_lead()` parses the LLM reply as a versioned JSON
# contract (metadata + classification required) instead of accepting any free
# text; a non-JSON reply now yields the terminal 'parse_failure' status. These
# concurrency tests care about failure isolation and every lead reaching a
# terminal status, not about the enrichment payload, so they feed the smallest
# contract that parses cleanly to a 'completed' result.
_VALID_CONTRACT = json.dumps({
    'metadata': {'schema_version': '1.0'},
    'classification': {'entity_type': 'b2b_company', 'confidence': 'low'},
})


class _SyncExecutor:
    """Test-only stand-in for ThreadPoolExecutor.

    _cron_enrich_leads()'s real ThreadPoolExecutor + per-lead
    self.env.registry.cursor() is the correct, standard Odoo pattern for
    parallel background-job fan-out in production. But TransactionCase
    wraps the whole test method in one shared, uncommitted transaction with
    its own internal locking, and a genuinely concurrent worker thread
    contends with that machinery and deadlocks (confirmed live: two
    connections stuck "idle in transaction" for 100+ seconds, blocked in
    Python -- not on a Postgres lock -- while running the exact same
    "verify column" query that also stalled during an earlier, unrelated
    real-cursor experiment). Running each lead's worker function
    synchronously in the test's own thread sidesteps that contention
    entirely (a single thread opening several cursors in sequence, one at a
    time, is the same safe pattern Task 4's migration script already uses)
    while still exercising the real per-lead-cursor/commit/failure-isolation
    logic -- it just isn't run concurrently during the test.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def map(self, func, iterable):
        return [func(item) for item in iterable]


class TestCronConcurrency(TransactionCase):
    """Odoo's TransactionCase forbids cr.commit()/cr.rollback() on self.env.cr
    (it would break the class-shared savepoint every sibling test relies on),
    so leads are created and committed through a genuinely separate cursor —
    the same "open another cursor" escape hatch the framework's own
    AssertionError message points to. Real, committed rows are required here
    because _cron_enrich_leads() gives each worker its own cursor, and a
    worker's separate connection can never see another connection's
    uncommitted writes."""

    def setUp(self):
        super().setUp()
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            Lead = env['crm.lead']

            # This runs against a shared, already-populated demo database, not
            # a throwaway CI database. _cron_enrich_leads()'s search domain
            # (auto_enrich=True, status != processing) is unscoped -- it would
            # also sweep up any other pre-existing lead that happens to match
            # (auto_enrich is opt-in, but older/pre-existing rows may still
            # carry auto_enrich=True from before it defaulted to False).
            # Temporarily
            # mark those excluded (by flipping them to 'processing', which the
            # same domain excludes) so this test's _cron_enrich_leads() call
            # only ever touches its own 3 fixture leads; restore their real
            # status in cleanup.
            other_matching = Lead.search([
                ('auto_enrich', '=', True),
                ('ai_enrichment_status', '!=', 'processing'),
            ])
            self._other_lead_original_status = {lead.id: lead.ai_enrichment_status for lead in other_matching}
            other_matching.write({'ai_enrichment_status': 'processing'})

            leads = Lead.create([
                {'name': 'Lead A', 'partner_name': 'Acme A', 'auto_enrich': True},
                {'name': 'Lead B', 'partner_name': 'Acme B', 'auto_enrich': True},
                {'name': 'Lead C', 'partner_name': 'Acme C', 'auto_enrich': True},
            ])
            self.lead_ids = leads.ids
            cr.commit()
        self.leads = self.env['crm.lead'].browse(self.lead_ids)
        self.addCleanup(self._cleanup_committed_leads)

    def _cleanup_committed_leads(self):
        """The leads above were committed on a separate connection, so they
        survive this test's own rollback -- delete them the same way so no
        fake leads accumulate in the shared database across test runs, and
        restore any other pre-existing lead's real status."""
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            env['crm.lead'].browse(self.lead_ids).unlink()
            for lead_id, status in self._other_lead_original_status.items():
                env['crm.lead'].browse(lead_id).write({'ai_enrichment_status': status})
            cr.commit()

    def _run_cron(self):
        """_cron_enrich_leads()'s own self.search() must also run through a
        fresh cursor/environment, not self.env. TransactionCase shares ONE
        transaction across every test method in this class (savepoints only
        isolate rollback, not the REPEATABLE READ snapshot), so self.env's
        snapshot is frozen at whichever test method happens to run first --
        confirmed live: a second test method's self.search() still returned
        the first test method's already-deleted lead ids instead of its own
        freshly committed ones. A real production cron invocation always
        gets a brand-new environment; only this test harness's class-shared
        transaction makes routing around self.env necessary here."""
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            env['crm.lead']._cron_enrich_leads()

    def _read_statuses(self):
        """Odoo sets ISOLATION_LEVEL_REPEATABLE_READ on every connection
        (odoo/sql_db.py), including self.env.cr. That means self.env's
        snapshot was taken before _cron_enrich_leads()'s worker committed its
        writes on a separate connection -- no amount of invalidate_recordset()
        can make self.env see them, because REPEATABLE READ freezes
        visibility at transaction start, not at query time. Reading back
        through a brand new cursor (a fresh snapshot) is the only way to
        observe another connection's already-committed writes."""
        with Registry(self.env.cr.dbname).cursor() as cr:
            env = api.Environment(cr, self.env.uid, self.env.context)
            return {lead.id: lead.ai_enrichment_status for lead in env['crm.lead'].browse(self.lead_ids)}

    def test_cron_enrich_leads_all_reach_terminal_status(self):
        with patch(
            'odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search',
            return_value={'success': True, 'results': [], 'providers_used': [], 'cache_hits': 0, 'latency_ms': 0},
        ), patch(
            'odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm',
            return_value={'success': True, 'content': _VALID_CONTRACT, 'error': None, 'retries': 0},
        ), patch(
            'odoo.addons.sgc_lead_scoring.models.crm_lead.ThreadPoolExecutor', _SyncExecutor,
        ):
            self._run_cron()

        statuses = self._read_statuses()
        for lead_id, status in statuses.items():
            self.assertIn(status, ('completed', 'partial', 'failed'), 'lead %s status=%s' % (lead_id, status))
            self.assertNotEqual(status, 'pending')
            self.assertNotEqual(status, 'processing')

    def test_cron_enrich_leads_one_failure_does_not_block_others(self):
        call_count = {'n': 0}

        def flaky_call_llm(*a, **kw):
            call_count['n'] += 1
            if call_count['n'] == 2:
                raise Exception('simulated provider outage')
            return {'success': True, 'content': _VALID_CONTRACT, 'error': None, 'retries': 0}

        with patch(
            'odoo.addons.sgc_lead_scoring.models.web_research_service.WebResearchService.multi_search',
            return_value={'success': True, 'results': [], 'providers_used': [], 'cache_hits': 0, 'latency_ms': 0},
        ), patch(
            'odoo.addons.sgc_lead_scoring.models.llm_service.LlmService.call_llm',
            side_effect=flaky_call_llm,
        ), patch(
            'odoo.addons.sgc_lead_scoring.models.crm_lead.ThreadPoolExecutor', _SyncExecutor,
        ):
            self._run_cron()

        statuses = list(self._read_statuses().values())
        self.assertIn('failed', statuses)
        self.assertIn('completed', statuses)
