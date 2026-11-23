# -*- coding: utf-8 -*-
"""Post-migrate for 19.0.1.6: seed a web.research.provider(type=google)
record from the legacy llm_lead_scoring.google_search_api_key /
..._google_search_engine_id config params, if they were set, so upgraded
installs keep working without re-entering credentials."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    config = env['ir.config_parameter'].sudo()
    api_key = config.get_param('llm_lead_scoring.google_search_api_key')
    engine_id = config.get_param('llm_lead_scoring.google_search_engine_id')
    if not api_key or not engine_id:
        return
    Provider = env['web.research.provider'].sudo()
    existing = Provider.with_context(active_test=False).search(
        [('provider_type', '=', 'google'), ('api_key', '=', api_key)], limit=1
    )
    if existing:
        return
    Provider.create({
        'name': 'Google Custom Search (migrated)',
        'sequence': 40,
        'provider_type': 'google',
        'api_key': api_key,
        'search_engine_id': engine_id,
        'daily_quota_limit': 100,
        'active': True,
    })
