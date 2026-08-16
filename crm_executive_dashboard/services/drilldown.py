# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
Click-through drill-down resolver.

Every KPI card, funnel stage, owner row, and campaign/source row in
the dashboard carries a ``data-drill`` payload (``type`` + ``key``).
When clicked, the JS posts that payload plus the current filter to
``/crm-dashboard/drilldown``; this module turns it into a concrete
``crm.lead`` (or ``utm.campaign``) domain so the controller can build
a standard ``ir.actions.act_window`` and the JS can open it.

This is intentionally a thin, declarative mapping rather than a
generic query builder: every drill target below corresponds to a
domain that is already computed elsewhere in ``crm.dashboard.kpi``
(kept in sync by hand) -- so what you click is exactly what you see.
"""

from odoo import _, fields
from odoo.addons.crm_executive_dashboard.models.crm_dashboard_kpi import _build_domain


def resolve(env, drill_type, drill_key, filter_dict):
    """Return ``{'model', 'domain', 'name'}`` or ``None`` if not drillable."""
    won_stage_ids = env['crm.dashboard.kpi']._get_won_stage_ids()

    if drill_type == 'kpi':
        return _resolve_kpi(env, drill_key, filter_dict, won_stage_ids)
    if drill_type == 'funnel_stage':
        try:
            stage_id = int(drill_key)
        except (TypeError, ValueError):
            return None
        domain = _build_domain(filter_dict, 'create_date') + [
            ('type', '=', 'opportunity'), ('stage_id', '=', stage_id),
        ]
        stage = env['crm.stage'].browse(stage_id)
        return {'model': 'crm.lead', 'domain': domain, 'name': _('Pipeline: %s') % (stage.name or '')}
    if drill_type == 'owner':
        try:
            user_id = int(drill_key)
        except (TypeError, ValueError):
            user_id = False
        domain = _build_domain(filter_dict, 'create_date') + [
            ('type', '=', 'opportunity'), ('user_id', '=', user_id),
        ]
        name = env['res.users'].browse(user_id).name if user_id else _('Unassigned')
        return {'model': 'crm.lead', 'domain': domain, 'name': _('Opportunities: %s') % name}
    if drill_type == 'source':
        source_id = drill_key
        try:
            source_id = int(source_id) if source_id not in (False, 'false', '', None) else False
        except (TypeError, ValueError):
            source_id = False
        domain = _build_domain(filter_dict, 'create_date') + [('source_id', '=', source_id)]
        name = env['utm.source'].browse(source_id).name if source_id else _('Undefined')
        return {'model': 'crm.lead', 'domain': domain, 'name': _('Leads from: %s') % name}
    if drill_type == 'campaign':
        try:
            campaign_id = int(drill_key)
        except (TypeError, ValueError):
            return None
        domain = _build_domain(filter_dict, 'create_date') + [('campaign_id', '=', campaign_id)]
        campaign = env['utm.campaign'].browse(campaign_id)
        return {'model': 'crm.lead', 'domain': domain, 'name': _('Leads: %s') % (campaign.title or campaign.name or '')}
    return None


def _resolve_kpi(env, key, filter_dict, won_stage_ids):
    lead_domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'lead')]
    opp_domain = _build_domain(filter_dict, 'date_open') + [('type', '=', 'opportunity')]

    mapping = {
        'leads_total': (lead_domain, _('All Leads')),
        'leads_new_today': (
            _build_domain({'period': 'today'}, 'create_date') + [('type', '=', 'lead')],
            _('New Leads — Today')),
        'leads_new_week': (
            _build_domain({'period': 'last_7_days'}, 'create_date') + [('type', '=', 'lead')],
            _('New Leads — This Week')),
        'leads_new_month': (
            _build_domain({'period': 'current_month'}, 'create_date') + [('type', '=', 'lead')],
            _('New Leads — This Month')),
        'leads_qualified': (
            lead_domain + [('date_open', '!=', False)], _('Qualified Leads')),
        'opps_open': (opp_domain + [('date_closed', '=', False)], _('Open Opportunities')),
        'opps_won': (opp_domain + [('stage_id', 'in', won_stage_ids)], _('Won Opportunities')),
        'opps_lost': (
            _build_domain(filter_dict, 'date_open', include_inactive=True) + [
                ('type', '=', 'opportunity'), ('active', '=', False), ('probability', '=', 0),
            ], _('Lost Opportunities')),
        'revenue_pipeline': (
            opp_domain + [('date_closed', '=', False)], _('Pipeline Opportunities')),
        'revenue_won': (
            opp_domain + [('stage_id', 'in', won_stage_ids)], _('Won Revenue — Opportunities')),
        'stale_opps': (
            _build_domain(filter_dict, 'create_date') + [
                ('type', '=', 'opportunity'), ('date_closed', '=', False),
            ], _('Stale / Aging Opportunities')),
        'overdue_followups': (
            _build_domain(filter_dict, 'create_date') + [
                ('activity_ids.date_deadline', '<', fields.Date.today()),
            ], _('Overdue Follow-ups')),
        'untouched': (
            lead_domain, _('Untouched (New Stage) Leads')),
        'active_opps': (
            _build_domain(filter_dict, 'create_date') + [('type', '=', 'opportunity'), ('active', '=', True)],
            _('Active Opportunities')),
    }
    entry = mapping.get(key)
    if not entry:
        return None
    domain, name = entry
    return {'model': 'crm.lead', 'domain': domain, 'name': name}
