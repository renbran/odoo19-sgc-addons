# -*- coding: utf-8 -*-
import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from odoo import models, api

_logger = logging.getLogger(__name__)

_DEFAULT_NUM_RESULTS = 5

# Live deployments source provider credentials from environment variables
# rather than the ir/web.research.provider api_key field, so real keys never
# touch the database or git. Falls back to provider.api_key (e.g. tests,
# or an admin who prefers DB-stored credentials).
_ENV_KEY_VAR = {
    'tavily': 'TAVILY_API_KEY',
    'exa': 'EXA_API_KEY',
    'serper': 'SERPER_API_KEY',
    'serpapi': 'SERPAPI_API_KEY',
    'google': 'GOOGLE_API_KEY',
}


class WebResearchService(models.Model):
    _name = 'web.research.service'
    _description = 'Web Research Orchestrator'

    @api.model
    def hash_query(self, query):
        return hashlib.sha256(query.encode('utf-8')).hexdigest()

    @api.model
    def anonymize_lead_id(self, lead_id):
        return hashlib.sha256(str(lead_id).encode('utf-8')).hexdigest()

    @api.model
    def search(self, query, num_results=_DEFAULT_NUM_RESULTS, providers=None):
        """Single-query search. multi_search() fans this out across queries."""
        prepared = self._prepare_query(query, num_results, providers)
        outcome = self._run_provider_call(prepared, num_results)
        return self._finalize_result(outcome)

    def _prepare_query(self, query, num_results, providers):
        """Main-thread-only phase: cache lookup + provider selection (DB reads).

        Never call this from a worker thread — it uses self.env.
        """
        query_hash = self.hash_query(query)
        cached = self.env['web.research.result'].get_cached(query_hash)
        if cached:
            return {'query': query, 'query_hash': query_hash, 'phase': 'cache_hit', 'cached': cached}

        chain = self.env['web.research.provider'].get_available_chain(provider_types=providers)
        if not chain:
            return {'query': query, 'query_hash': query_hash, 'phase': 'no_provider'}

        provider = chain[0]
        env_var = _ENV_KEY_VAR.get(provider.provider_type)
        api_key = (os.environ.get(env_var) if env_var else None) or provider.api_key
        provider_config = {
            'provider_type': provider.provider_type,
            'api_key': api_key,
            'base_url': provider.base_url,
            'search_engine_id': provider.search_engine_id,
        }
        return {
            'query': query,
            'query_hash': query_hash,
            'phase': 'call_provider',
            'provider': provider,
            'provider_config': provider_config,
        }

    def _run_provider_call(self, prepared, num_results):
        """Safe to run in a worker thread: touches only plain data (provider_config,
        query, num_results) and the `requests` library — never self.env or any
        Odoo recordset. This is the only phase multi_search() parallelizes.
        """
        if prepared['phase'] != 'call_provider':
            return prepared
        start = time.monotonic()
        results, success, status_code = self._call_provider(prepared['provider_config'], prepared['query'], num_results)
        latency_ms = int((time.monotonic() - start) * 1000)
        return {**prepared, 'results': results, 'success': success, 'status_code': status_code, 'latency_ms': latency_ms}

    def _finalize_result(self, outcome):
        """Main-thread-only phase: circuit breaker, audit log, cache write (DB writes).

        Never call this from a worker thread — it uses self.env and mutates
        ORM recordsets.
        """
        if outcome['phase'] == 'cache_hit':
            cached = outcome['cached']
            return {
                'success': True,
                'results': json.loads(cached.results_json),
                'providers_used': cached.providers_used.split(',') if cached.providers_used else [],
                'cache_hit': True,
                'latency_ms': 0,
            }

        if outcome['phase'] == 'no_provider':
            _logger.info('web.research.service: no available provider for query_hash=%s', outcome['query_hash'])
            return {
                'success': False,
                'results': [],
                'providers_used': [],
                'cache_hit': False,
                'latency_ms': 0,
                'reason': 'all_providers_unavailable',
            }

        provider = outcome['provider']
        success = outcome['success']
        status_code = outcome.get('status_code')
        results = outcome['results']
        latency_ms = outcome['latency_ms']
        query_hash = outcome['query_hash']
        query = outcome['query']

        if status_code == 429:
            provider.sudo().write({'daily_quota_used': provider.daily_quota_limit})
        elif status_code in (401, 403):
            self._disable_provider_and_notify(provider)

        provider.record_call(success)
        self.env['web.research.audit'].log_call(provider, query_hash, None, success, latency_ms, len(results))

        if success:
            for r in results:
                r['_provider'] = provider.provider_type
            self.env['web.research.result'].store(query_hash, query, results, provider.provider_type)

        return {
            'success': success,
            'results': results,
            'providers_used': [provider.provider_type] if success else [],
            'cache_hit': False,
            'latency_ms': latency_ms,
            'reason': None if success else 'provider_call_failed',
        }

    def _disable_provider_and_notify(self, provider):
        """Main-thread-only: deactivate a provider that failed authentication
        and post a to-do activity for every system-admin user."""
        provider.sudo().write({'active': False})
        admins = self.env['res.users'].sudo().search([('all_group_ids', '=', self.env.ref('base.group_system').id)])
        for admin in admins:
            self.env['mail.activity'].sudo().create({
                'res_model_id': self.env['ir.model']._get_id('web.research.provider'),
                'res_id': provider.id,
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': 'Web research provider disabled: authentication failed',
                'note': 'Provider "%s" returned 401/403 and was disabled. Update its credentials.' % provider.name,
                'user_id': admin.id,
            })

    def _run_search_round(self, queries, parallel, num_results, providers):
        """Runs prepare -> (parallel) HTTP call -> finalize for a batch of
        queries. Used by multi_search() for both the initial pass and the
        relaxed-query retry, so both passes get the same thread-safety
        guarantees (only _run_provider_call ever runs on a worker thread).
        """
        prepared_list = [self._prepare_query(q, num_results, providers) for q in queries]
        if parallel:
            with ThreadPoolExecutor(max_workers=min(len(queries), 5) or 1) as executor:
                futures = [executor.submit(self._run_provider_call, p, num_results) for p in prepared_list]
                outcomes = [f.result() for f in futures]
        else:
            outcomes = [self._run_provider_call(p, num_results) for p in prepared_list]
        return [self._finalize_result(o) for o in outcomes]

    @api.model
    def multi_search(self, queries, parallel=True, num_results=_DEFAULT_NUM_RESULTS, min_results=3, providers=None):
        cache_hits = 0
        providers_used = set()
        all_raw_results = []

        per_query_results = self._run_search_round(queries, parallel, num_results, providers)

        for res in per_query_results:
            if res.get('cache_hit'):
                cache_hits += 1
            providers_used.update(res.get('providers_used', []))
            all_raw_results.extend(res.get('results', []))

        merged = self._dedupe_by_domain(all_raw_results)
        total_latency_ms = sum(r.get('latency_ms', 0) for r in per_query_results)

        if len(merged) < min_results:
            relaxed_queries = [' '.join(q.split()[:3]) for q in queries]
            retry_results = self._run_search_round(relaxed_queries, parallel, num_results, providers)
            for res in retry_results:
                if res.get('cache_hit'):
                    cache_hits += 1
                providers_used.update(res.get('providers_used', []))
                all_raw_results.extend(res.get('results', []))
            merged = self._dedupe_by_domain(all_raw_results)
            total_latency_ms += sum(r.get('latency_ms', 0) for r in retry_results)
            _logger.info(
                'web.research.service.multi_search: relaxed-query retry produced %d results',
                len(merged),
            )

        return {
            'success': bool(merged) or any(r['success'] for r in per_query_results),
            'results': merged,
            'providers_used': sorted(providers_used),
            'cache_hits': cache_hits,
            'latency_ms': total_latency_ms,
        }

    def _dedupe_by_domain(self, results):
        by_domain = {}
        for r in results:
            url = r.get('url') or ''
            domain = url.split('//')[-1].split('/')[0].lower()
            if not domain:
                continue
            if domain not in by_domain:
                merged = dict(r)
                merged['sources'] = [r.get('_provider', 'unknown')]
                by_domain[domain] = merged
            else:
                by_domain[domain]['sources'].append(r.get('_provider', 'unknown'))
        return list(by_domain.values())

    @api.model
    def search_google_custom(self, query, num_results=_DEFAULT_NUM_RESULTS):
        """Backward-compat shim: pre-redesign callers (google.search.setup.wizard)
        keep this exact signature; it now delegates to the orchestrator restricted
        to the google provider type."""
        return self.search(query, num_results=num_results, providers=['google'])

    def _call_provider(self, provider_config, query, num_results):
        """provider_config is a plain dict (see _prepare_query) — this method
        and everything it calls must never touch self.env, so it is safe to
        run from a ThreadPoolExecutor worker thread.
        """
        dispatch = {
            'tavily': self._call_tavily,
            'exa': self._call_exa,
            'serper': self._call_serper,
            'serpapi': self._call_serpapi,
            'searxng': self._call_searxng,
            'google': self._call_google,
        }
        handler = dispatch.get(provider_config['provider_type'])
        if not handler:
            _logger.warning('web.research.service: unknown provider_type %s', provider_config['provider_type'])
            return [], False, None
        try:
            return handler(provider_config, query, num_results)
        except requests.RequestException as exc:
            query_hash = self.hash_query(query)
            _logger.warning(
                'web.research.service: %s request failed (%s) for query_hash=%s',
                provider_config['provider_type'], type(exc).__name__, query_hash,
            )
            return [], False, None

    def _call_tavily(self, provider_config, query, num_results):
        resp = requests.post(
            'https://api.tavily.com/search',
            json={'api_key': provider_config['api_key'], 'query': query, 'max_results': num_results},
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')}
            for r in data.get('results', [])[:num_results]
        ]
        return results, True, resp.status_code

    def _call_exa(self, provider_config, query, num_results):
        resp = requests.post(
            'https://api.exa.ai/search',
            json={'query': query, 'numResults': num_results},
            headers={'x-api-key': provider_config['api_key']},
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('text')}
            for r in data.get('results', [])[:num_results]
        ]
        return results, True, resp.status_code

    def _call_serper(self, provider_config, query, num_results):
        resp = requests.post(
            'https://google.serper.dev/search',
            json={'q': query, 'num': num_results},
            headers={'X-API-KEY': provider_config['api_key']},
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('link'), 'snippet': r.get('snippet')}
            for r in data.get('organic', [])[:num_results]
        ]
        return results, True, resp.status_code

    def _call_serpapi(self, provider_config, query, num_results):
        resp = requests.get(
            'https://serpapi.com/search',
            params={
                'engine': 'google',
                'api_key': provider_config['api_key'],
                'q': query,
                'num': num_results,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('link'), 'snippet': r.get('snippet')}
            for r in data.get('organic_results', [])[:num_results]
        ]
        return results, True, resp.status_code

    def _call_searxng(self, provider_config, query, num_results):
        resp = requests.get(
            provider_config['base_url'],
            params={'q': query, 'format': 'json'},
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('url'), 'snippet': r.get('content')}
            for r in data.get('results', [])[:num_results]
        ]
        return results, True, resp.status_code

    def _call_google(self, provider_config, query, num_results):
        resp = requests.get(
            'https://www.googleapis.com/customsearch/v1',
            params={
                'key': provider_config['api_key'],
                'cx': provider_config['search_engine_id'],
                'q': query,
                'num': min(num_results, 10),
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return [], False, resp.status_code
        data = resp.json()
        results = [
            {'title': r.get('title'), 'url': r.get('link'), 'snippet': r.get('snippet')}
            for r in data.get('items', [])[:num_results]
        ]
        return results, True, resp.status_code
