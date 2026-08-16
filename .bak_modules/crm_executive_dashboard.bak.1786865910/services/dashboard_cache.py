# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
Dashboard cache service.

Public API
----------

    from odoo.addons.crm_executive_dashboard.services.dashboard_cache import (
        get_or_compute, invalidate,
    )

    payload = get_or_compute(env, filter_dict)

The cache has two tiers:

1. **Request-scoped** (in-process, on the request object): always on.
   This means a controller that calls `get_or_compute()` five times in
   one request only triggers one collect_all().

2. **Persistent** (stored in ``ir.config_parameter`` with a TTL):
   opt-in via the system parameter
   ``crm_executive_dashboard.cache_ttl_seconds`` (default 0 = disabled).
   When enabled, the same filter_dict within the TTL window returns the
   previously computed payload from the parameter store, skipping the
   ORM entirely. Useful for high-traffic dashboards where the same
   filters are re-requested many times per minute.

Safety guarantees
-----------------
* Cache is keyed on a SHA-256 of the serialised filter dict; collisions
  are astronomically unlikely.
* TTL is enforced strictly — expired entries are recomputed.
* Any exception in the compute path is logged and re-raised; the cache
  never silently returns stale data on error.
* The cache is **never** used for any user-specific data; all aggregates
  are global CRM metrics. If user-specific caching is added later, the
  user id must be folded into the cache key.
"""

import json
import logging
import time
import hashlib
from collections import OrderedDict

from odoo import api, tools

_logger = logging.getLogger(__name__)

# System parameter names
_PARAM_TTL = 'crm_executive_dashboard.cache_ttl_seconds'
_PARAM_CACHE = 'crm_executive_dashboard.persistent_cache'

# Default: caching off (0). Set to e.g. 30 in production for 30-second cache.
DEFAULT_TTL = 0

# Maximum number of in-process request-cached entries. Beyond this, the
# LRU evicts. 32 covers typical multi-section page renders.
MAX_REQUEST_ENTRIES = 32


def _stable_key(filter_dict):
    """Hash the filter dict to a stable cache key.

    We serialise with ``sort_keys=True`` so equivalent dicts (e.g.
    ``{'a': 1, 'b': 2}`` vs ``{'b': 2, 'a': 1}``) produce the same key.
    """
    try:
        canonical = json.dumps(
            filter_dict or {},
            sort_keys=True,
            default=str,
            separators=(',', ':'),
        )
    except (TypeError, ValueError):
        # Filter contained something unserialisable — fall back to repr.
        canonical = repr(sorted((filter_dict or {}).items()))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _get_request_cache(request):
    """Return the in-process cache attached to the request, creating it
    lazily. Returns an ``OrderedDict`` (LRU)."""
    if request is None:
        return None
    cache_attr = '_ced_request_cache'
    if not hasattr(request, cache_attr):
        cache = OrderedDict()
        setattr(request, cache_attr, cache)
        return cache
    return getattr(request, cache_attr)


def _get_ttl(env):
    """Read the TTL from ir.config_parameter. Returns int seconds."""
    try:
        value = env['ir.config_parameter'].sudo().get_param(_PARAM_TTL, DEFAULT_TTL)
        return int(value or 0)
    except (TypeError, ValueError):
        return DEFAULT_TTL


def get_or_compute(env, filter_dict, force_refresh=False):
    """Return the dashboard payload, using cache when possible.

    Parameters
    ----------
    env : odoo.api.Environment
        The current request's environment.
    filter_dict : dict
        The filter state (period, salesperson, team, etc.).
    force_refresh : bool
        If True, bypass both cache tiers and recompute.

    Returns
    -------
    dict
        The payload produced by ``CrmDashboardKpi.collect_all()``.
    """
    key = _stable_key(filter_dict)
    request = getattr(env, 'request', None)

    # Tier 1: request-scoped LRU cache
    req_cache = _get_request_cache(request)
    if not force_refresh and req_cache is not None and key in req_cache:
        # LRU: move to end
        req_cache.move_to_end(key)
        return req_cache[key]

    # Tier 2: persistent cache (ir.config_parameter with TTL)
    if not force_refresh:
        ttl = _get_ttl(env)
        if ttl > 0:
            payload = _read_persistent(env, key, ttl)
            if payload is not None:
                _store_request(req_cache, key, payload)
                return payload

    # Cache miss — compute
    start = time.monotonic()
    try:
        payload = env['crm.dashboard.kpi'].collect_all(filter_dict or {})
    except Exception as e:
        _logger.exception("CED: collect_all() failed for key %s: %s", key[:8], e)
        raise
    duration = (time.monotonic() - start) * 1000.0
    _logger.info("CED: collect_all() took %.1fms for key %s", duration, key[:8])

    # Store in both caches
    _store_request(req_cache, key, payload)
    if _get_ttl(env) > 0:
        _write_persistent(env, key, payload)
    return payload


def invalidate(env=None, filter_dict=None):
    """Invalidate cache entries.

    With no arguments, clears all persistent cache. With a filter_dict,
    clears the matching key in the request cache (if any).
    """
    # Persistent cache
    if env is not None:
        ICP = env['ir.config_parameter'].sudo()
        if filter_dict is None:
            # Wipe all CED persistent cache entries
            keys = ICP.search([('key', '=like', f'{_PARAM_CACHE}.%')])
            if keys:
                keys.unlink()
                _logger.info("CED: invalidated %d persistent cache entries", len(keys))
        else:
            key = _stable_key(filter_dict)
            ICP.search([('key', '=', f'{_PARAM_CACHE}.{key}')]).unlink()

    # Request cache: cannot be cleared across requests — leave it. The
    # next request will rebuild it on demand.


def _store_request(req_cache, key, payload):
    if req_cache is None:
        return
    req_cache[key] = payload
    req_cache.move_to_end(key)
    # LRU evict
    while len(req_cache) > MAX_REQUEST_ENTRIES:
        req_cache.popitem(last=False)


def _read_persistent(env, key, ttl):
    ICP = env['ir.config_parameter'].sudo()
    row = ICP.search_read(
        [('key', '=', f'{_PARAM_CACHE}.{key}')],
        fields=['value', 'write_date'],
    )
    if not row:
        return None
    # TTL check
    try:
        written = fields.Datetime.from_string(row[0]['write_date'])
        age = (fields.Datetime.now() - written).total_seconds()
        if age > ttl:
            return None
    except Exception:
        return None
    # Decode JSON
    try:
        return json.loads(row[0]['value'])
    except (TypeError, ValueError):
        _logger.warning("CED: corrupt persistent cache for key %s, evicting", key[:8])
        ICP.search([('key', '=', f'{_PARAM_CACHE}.{key}')]).unlink()
        return None


def _write_persistent(env, key, payload):
    ICP = env['ir.config_parameter'].sudo()
    full_key = f'{_PARAM_CACHE}.{key}'
    try:
        value = json.dumps(payload, default=str, separators=(',', ':'))
    except (TypeError, ValueError) as e:
        _logger.warning("CED: cannot serialise payload for cache: %s", e)
        return
    # Cap size to 1 MB to avoid bloating parameter table
    if len(value) > 1_048_576:
        _logger.info("CED: payload too large for persistent cache (%d bytes)", len(value))
        return
    existing = ICP.search([('key', '=', full_key)])
    if existing:
        existing.write({'value': value})
    else:
        ICP.create({'key': full_key, 'value': value})


# Import inside the module to avoid circulars
from odoo import fields  # noqa: E402
