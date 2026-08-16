# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
Service layer for the CRM Executive Dashboard.

The KPI compute engine (models/crm_dashboard_kpi.py) does the heavy lifting
via read_group, but doing 30+ read_group calls on every page load is wasteful
when the filter hasn't changed. The cache service here:

  1. Memoises the collect_all() result for the duration of a single HTTP
     request (request-scoped cache stored on the request object).
  2. Optionally persists high-level aggregates in ir.config_parameter with
     a TTL so repeat page loads hit the cache (toggle via system param).
  3. Never invalidates manually — TTL expiry is the only eviction. This
     keeps the implementation trivial and safe.

The cache key is the filter dict serialised to JSON in stable order.
"""

from . import dashboard_cache
from . import chart_data

__all__ = ['dashboard_cache', 'chart_data']
