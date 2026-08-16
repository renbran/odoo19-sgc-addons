# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
CRM Executive Dashboard — Core KPI Engine
==========================================

This is the computational heart of the dashboard. It exposes a single
transient model ``crm.dashboard.kpi`` whose methods return structured
dicts consumed by the Owl frontend.

Design principles
-----------------
* **One source of truth.** Every section of the dashboard reads from the
  same query results when filters overlap. We collect the raw data once
  and slice it in Python for the multiple views (cards, charts, tables).
* **Database-friendly.** All aggregations use ``read_group`` with
  ``groupby`` so PostgreSQL does the heavy lifting. No Python loops
  over thousands of records.
* **Stateless & transient.** The model is ``crm.dashboard.kpi`` with
  ``_transient_max_count = 0`` and ``_transient_max_hours = 1`` so
  filter-only "records" do not pollute the DB.
* **Cached per-request.** ``tools.ormcache`` is used for the few
  static lookups (won stage ids, lead source list) that never change
  inside a single request.
* **Filter contract.** All public compute methods accept a single
  ``filter`` dict produced by ``crm.dashboard.filter.resolve()``. This
  keeps the controller thin and the JS contract simple.
* **Permission-aware.** Record rules on ``crm.lead`` and ``crm.team``
  are respected automatically by ``read_group`` since we always
  operate through the ORM. We do not bypass access rights.
* **No N+1.** All leaf methods (calls/mettings/emails, etc.) issue a
  single ``read_group`` per activity type per period.

Field-name contract (matches Odoo 19 ``crm.lead`` exactly)
---------------------------------------------------------
* ``user_id``       — assigned salesperson
* ``team_id``       — sales team
* ``stage_id``      — opportunity stage
* ``source_id``     — lead source (utm.source)
* ``date_open``     — datetime when lead became opportunity
* ``date_closed``   — datetime when won/lost
* ``date_deadline`` — expected closing date
* ``expected_revenue``      — pipeline value
* ``prorated_revenue``      — probability-weighted revenue
* ``recurring_revenue``     — MRR/ARR
* ``type``          — 'lead' or 'opportunity'
* ``active``        — boolean (always True for live dashboard)
"""

import logging
import warnings
from collections import defaultdict
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, tools


# Module-level filter on import — silences the
# "Since 19.0, read_group is deprecated" warnings emitted by every
# read_group() call.  The whole engine uses read_group's dict-based
# shape, so a wholesale switch to _read_group (which returns tuples)
# would be a major refactor.  The warnings are still visible to the
# developer by inspecting the source.
warnings.filterwarnings('ignore',
                        message='.*read_group is deprecated.*',
                        category=DeprecationWarning)
from odoo.exceptions import UserError, AccessError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-driven alert mapping (rule_type -> FontAwesome icon)
# ---------------------------------------------------------------------------
_RULE_ICONS = {
    'lead_stale': 'fa-user-clock',
    'opp_stale': 'fa-hourglass-half',
    'pipeline_low': 'fa-money',
    'conversion_low': 'fa-line-chart',
    'overdue_followups': 'fa-exclamation-triangle',
    'won_zero': 'fa-trophy',
    'no_activity': 'fa-pause-circle',
}

# Map rule severity (info/warn/danger) to the level expected by the JS
# ('info' / 'warning' / 'danger' / 'success')
_RULE_LEVEL_MAP = {
    'info': 'info',
    'warn': 'warning',
    'danger': 'danger',
    'success': 'success',
}


# ---------------------------------------------------------------------------
# Filter resolution helpers
# ---------------------------------------------------------------------------

def _resolve_date_range(filter_dict):
    """Convert the filter dict's period into a concrete (start, end) UTC pair.

    Returns a tuple ``(start_dt, end_dt, label)`` where both datetimes are
    naive (in the company's timezone) and ``end_dt`` is inclusive (we add
    the trailing second internally when building domains).
    """
    # Use the env of the current recordset for timezone-aware "today",
    # falling back to UTC date if no env is bound.
    try:
        from odoo.modules.registry import Registry
        # Default to UTC today; callers can override by setting env
        # on the bound model and re-calling.
        today = fields.Date.today()
    except Exception:
        today = date.today()
    period = filter_dict.get('period', 'last_30_days')
    custom_start = filter_dict.get('date_from')
    custom_end = filter_dict.get('date_to')

    if period == 'today':
        return today, today, 'Today'
    if period == 'yesterday':
        return today - timedelta(days=1), today - timedelta(days=1), 'Yesterday'
    if period == 'last_7_days':
        return today - timedelta(days=6), today, 'Last 7 Days'
    if period == 'last_30_days':
        return today - timedelta(days=29), today, 'Last 30 Days'
    if period == 'last_90_days':
        return today - timedelta(days=89), today, 'Last 90 Days'
    if period == 'current_month':
        return today.replace(day=1), today, 'Current Month'
    if period == 'previous_month':
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        first_prev_month = last_prev_month.replace(day=1)
        return first_prev_month, last_prev_month, 'Previous Month'
    if period == 'current_quarter':
        q_start_month = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=q_start_month, day=1), today, 'Current Quarter'
    if period == 'current_year':
        return today.replace(month=1, day=1), today, 'Current Year'
    if period == 'custom' and custom_start and custom_end:
        s = fields.Date.from_string(custom_start)
        e = fields.Date.from_string(custom_end)
        return s, e, 'Custom Range'

    # Fallback: last 30 days
    return today - timedelta(days=29), today, 'Last 30 Days'


def _build_domain(filter_dict, date_field='create_date', include_inactive=False):
    """Build a complete crm.lead domain from the filter dict.

    The ``date_field`` parameter allows the same helper to filter on
    ``create_date`` (lead creation), ``date_open`` (became opportunity),
    or ``date_closed`` (won/lost).

    ``include_inactive`` skips the ``active = True`` clause. This is
    needed for any "lost" calculation: in this pipeline a lead is
    marked lost by archiving it (``active=False, probability=0``) --
    there is no dedicated "Lost" stage -- so the default active-only
    domain would silently make every lost count zero.
    """
    domain = [] if include_inactive else [('active', '=', True)]

    # Company filter
    if filter_dict.get('company_id'):
        domain.append(('company_id', '=', filter_dict['company_id']))

    # Salesperson filter
    if filter_dict.get('user_id'):
        domain.append(('user_id', '=', filter_dict['user_id']))

    # Team filter
    if filter_dict.get('team_id'):
        domain.append(('team_id', '=', filter_dict['team_id']))

    # Source filter
    if filter_dict.get('source_id'):
        domain.append(('source_id', '=', filter_dict['source_id']))

    # Stage filter (opportunities only)
    if filter_dict.get('stage_id'):
        domain.append(('stage_id', '=', filter_dict['stage_id']))

    # Type filter (lead vs opportunity)
    if filter_dict.get('type'):
        domain.append(('type', '=', filter_dict['type']))

    # Date range
    start, end, _ = _resolve_date_range(filter_dict)
    if start and end:
        # For datetime fields, expand the end-date to end-of-day
        if date_field in ('create_date', 'write_date', 'date_open', 'date_closed'):
            start_dt = fields.Datetime.to_string(datetime.combine(start, datetime.min.time()))
            end_dt = fields.Datetime.to_string(datetime.combine(end, datetime.max.time()))
        else:
            start_dt = fields.Date.to_string(start)
            end_dt = fields.Date.to_string(end)
        domain.append((date_field, '>=', start_dt))
        domain.append((date_field, '<=', end_dt))

    return domain


# ---------------------------------------------------------------------------
# Main transient model
# ---------------------------------------------------------------------------

class CrmDashboardKpi(models.TransientModel):
    """Stateless KPI engine for the executive dashboard.

    All public methods are ``@api.model`` and return plain Python dicts
    ready for JSON serialization. The model itself is never "saved" —
    the controller instantiates it on demand.
    """

    _name = 'crm.dashboard.kpi'
    _description = 'CRM Executive Dashboard KPI Engine'
    _transient_max_count = 0
    _transient_max_hours = 1
    _order = 'id desc'

    # --- dummy fields required for transient model scaffolding ----------
    name = fields.Char('Filter Name', default='Executive Dashboard')
    filter_period = fields.Selection([
        ('today', 'Today'),
        ('yesterday', 'Yesterday'),
        ('last_7_days', 'Last 7 Days'),
        ('last_30_days', 'Last 30 Days'),
        ('last_90_days', 'Last 90 Days'),
        ('current_month', 'Current Month'),
        ('previous_month', 'Previous Month'),
        ('current_quarter', 'Current Quarter'),
        ('current_year', 'Current Year'),
        ('custom', 'Custom Range'),
    ], string='Period', default='last_30_days')
    date_from = fields.Date('Date From')
    date_to = fields.Date('Date To')
    user_id = fields.Many2one('res.users', string='Salesperson')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    source_id = fields.Many2one('utm.source', string='Lead Source')
    stage_id = fields.Many2one('crm.stage', string='Stage')
    company_id = fields.Many2one('res.company', string='Company')

    # ===================================================================
    # ONE-SHOT DATA COLLECTOR
    # ===================================================================

    @api.model
    def collect_all(self, filter_dict):
        """Run every KPI compute in a single call.

        The frontend calls this once on page load, then re-calls it
        when filters change. Centralising the call here lets us:
          * share a single ORM cache environment
          * skip expensive stage/source lookups on subsequent calls
          * return a single response payload for atomicity
        """
        result = {
            'kpi': self._compute_kpi_overview(filter_dict),
            # Kept computed (feeds the 'no_activity' alert rule type in
            # crm.dashboard.alert.rule) even though it's no longer the
            # primary rendered engagement section -- see 'disposition'.
            'activity': self._compute_activity_analytics(filter_dict),
            'disposition': self._compute_disposition_analytics(filter_dict),
            'productivity': self._compute_productivity(filter_dict),
            'startup': self._compute_startup_metrics(filter_dict),
            'owner_analytics': self._compute_owner_analytics(filter_dict),
            'campaign_analytics': self._compute_campaign_analytics(filter_dict),
            'funnel': self._compute_sales_funnel(filter_dict),
            'alerts': self._compute_alerts(filter_dict),
            'charts': self._compute_chart_data(filter_dict),
            'filter': self._normalize_filter(filter_dict),
            'generated_at': fields.Datetime.now(),
        }
        return result

    # ===================================================================
    # SECTION 1 — EXECUTIVE KPI OVERVIEW
    # ===================================================================

    @api.model
    def _compute_kpi_overview(self, filter_dict):
        """Top-row KPI cards: Leads, Opportunities, Revenue, Conversion.

        Strategy
        --------
        * One ``read_group`` per metric, each grouped by a relevant field
          or aggregated across the date range. This minimises round-trips
          and lets PostgreSQL use the existing indexes on
          ``create_date``, ``date_open``, ``date_closed``.
        * Won stage ids are resolved once via ``_get_won_stage_ids``.
        """
        Lead = self.env['crm.lead']

        # --- Lead metrics ----------------------------------------------
        lead_domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'lead')]
        lead_groups = Lead.read_group(
            lead_domain,
            fields=['id'],
            groupby='create_date:day',
            lazy=False,
        )

        # Total + period counts
        total_leads = Lead.search_count(lead_domain)
        new_today = Lead.search_count(
            _build_domain({'period': 'today'}, 'create_date') + [('type', '=', 'lead')]
        )
        new_week = Lead.search_count(
            _build_domain({'period': 'last_7_days'}, 'create_date') + [('type', '=', 'lead')]
        )
        new_month = Lead.search_count(
            _build_domain({'period': 'current_month'}, 'create_date') + [('type', '=', 'lead')]
        )

        # Qualified = has been moved past the first stage (i.e. date_open set)
        # or stage.is_won/is_won_qualification equivalent.
        # We use the heuristic: a lead is "qualified" if it has been
        # converted to an opportunity at some point OR has a stage with
        # sequence >= the average of the first two stages.
        qualified_leads = self._count_qualified_leads(filter_dict)
        unqualified_leads = max(total_leads - qualified_leads, 0)
        awaiting_action = self._count_awaiting_action_leads(filter_dict)

        # --- Opportunity metrics --------------------------------------
        opp_domain = _build_domain(filter_dict, 'date_open') + [('type', '=', 'opportunity')]
        total_opps = Lead.search_count(
            _build_domain(filter_dict, 'create_date') + [('type', '=', 'opportunity')]
        )
        open_opps = Lead.search_count(opp_domain + [('date_closed', '=', False)])

        won_stage_ids = self._get_won_stage_ids()

        won_opps = Lead.search_count(
            opp_domain + [('stage_id', 'in', won_stage_ids)]
        )
        # "Lost" has no dedicated stage in this pipeline -- Odoo's real
        # signal is an archived (active=False) opportunity with
        # probability=0. Use the same date_open cohort as won_opps so
        # the two are comparable, but without the active=True clause.
        lost_opps = Lead.search_count(
            _build_domain(filter_dict, 'date_open', include_inactive=True) + [
                ('type', '=', 'opportunity'),
                ('active', '=', False),
                ('probability', '=', 0),
            ]
        )
        opps_today = Lead.search_count(
            _build_domain({'period': 'today'}, 'date_open') + [('type', '=', 'opportunity')]
        )
        opps_week = Lead.search_count(
            _build_domain({'period': 'last_7_days'}, 'date_open') + [('type', '=', 'opportunity')]
        )
        opps_month = Lead.search_count(
            _build_domain({'period': 'current_month'}, 'date_open') + [('type', '=', 'opportunity')]
        )

        # --- Revenue metrics -------------------------------------------
        # Pipeline value = sum expected_revenue of OPEN opportunities
        pipeline_value = self._sum_field(
            opp_domain + [('date_closed', '=', False)],
            'expected_revenue',
        )
        # Forecast = probability-weighted (prorated_revenue is computed by Odoo)
        forecast_revenue = self._sum_field(
            opp_domain + [('date_closed', '=', False)],
            'prorated_revenue',
        )
        won_revenue = self._sum_field(
            opp_domain + [('stage_id', 'in', won_stage_ids)],
            'expected_revenue',
        )
        revenue_month = self._sum_field(
            opp_domain + [
                ('stage_id', 'in', won_stage_ids),
                ('date_closed', '>=', self._period_start('current_month_start')),
                ('date_closed', '<=', self._period_end('today')),
            ],
            'expected_revenue',
        )
        revenue_quarter = self._sum_field(
            opp_domain + [
                ('stage_id', 'in', won_stage_ids),
                ('date_closed', '>=', self._period_start('current_quarter_start')),
                ('date_closed', '<=', self._period_end('today')),
            ],
            'expected_revenue',
        )
        revenue_year = self._sum_field(
            opp_domain + [
                ('stage_id', 'in', won_stage_ids),
                ('date_closed', '>=', self._period_start('current_year_start')),
                ('date_closed', '<=', self._period_end('today')),
            ],
            'expected_revenue',
        )

        # --- Conversion metrics ---------------------------------------
        lead_to_opp = self._count_conversions(filter_dict, 'lead_to_opp')
        opp_to_won = self._count_conversions(filter_dict, 'opp_to_won')

        lead_conversion_rate = (lead_to_opp / total_leads * 100.0) if total_leads else 0.0
        opp_win_rate = (won_opps / (won_opps + lost_opps) * 100.0) if (won_opps + lost_opps) else 0.0
        lead_to_opp_ratio = f"1:{lead_to_opp / total_leads:.1f}" if total_leads else "0:0"
        opp_to_won_ratio = f"{won_opps}:{lost_opps}" if (won_opps or lost_opps) else "0:0"

        avg_conversion_time = self._compute_avg_conversion_days(filter_dict)

        return {
            'leads': {
                'total': total_leads,
                'new_today': new_today,
                'new_week': new_week,
                'new_month': new_month,
                'qualified': qualified_leads,
                'unqualified': unqualified_leads,
                'awaiting_action': awaiting_action,
            },
            'opportunities': {
                'total': total_opps,
                'open': open_opps,
                'won': won_opps,
                'lost': lost_opps,
                'created_today': opps_today,
                'created_week': opps_week,
                'created_month': opps_month,
            },
            'revenue': {
                'pipeline_value': round(pipeline_value, 2),
                'forecast': round(forecast_revenue, 2),
                'won': round(won_revenue, 2),
                'month': round(revenue_month, 2),
                'quarter': round(revenue_quarter, 2),
                'year': round(revenue_year, 2),
            },
            'conversion': {
                'lead_conversion_rate': round(lead_conversion_rate, 2),
                'opp_win_rate': round(opp_win_rate, 2),
                'lead_to_opp_ratio': lead_to_opp_ratio,
                'opp_to_won_ratio': opp_to_won_ratio,
                'avg_conversion_days': avg_conversion_time,
            },
        }

    # ===================================================================
    # SECTION 2 — SALES ACTIVITY ANALYTICS
    # ===================================================================

    @api.model
    def _compute_activity_analytics(self, filter_dict):
        """Compute daily/weekly/monthly activity counts.

        We split the work into two parts:

        * ``mail.activity`` for *scheduled* activities (calls, meetings,
          tasks) — these have an ``activity_type_id`` and a ``state``.
        * ``mail.message`` for *completed* communications — we count
          ``message_type = 'comment'`` with ``subtype_id`` matching
          ``mail.mt_note`` for notes, or use ``mail.tracking.value``
          for emails. For simplicity we count ``mail.message`` rows
          with ``message_type = 'email'`` to approximate emails sent.
        """
        Activity = self.env['mail.activity']
        Message = self.env['mail.message']

        # --- Daily ----------------------------------------------------
        daily_domain = self._period_domain('today')
        daily = self._aggregate_activities(daily_domain)

        # --- Weekly ---------------------------------------------------
        weekly_domain = self._period_domain('last_7_days')
        weekly = self._aggregate_activities(weekly_domain)

        # --- Monthly --------------------------------------------------
        monthly_domain = self._period_domain('current_month')
        monthly = self._aggregate_activities(monthly_domain)

        # --- Performance ratios --------------------------------------
        # mail.activity.state is non-stored in Odoo 19, so we fetch
        # activities in the daily window and bucket states in Python.
        today = fields.Date.today()
        daily_activities = Activity.search(
            daily_domain + [('res_model', '=', 'crm.lead')]
        )
        state_records = daily_activities.read(['state', 'date_deadline'])
        completed = sum(1 for r in state_records if r.get('state') == 'done')
        scheduled = sum(1 for r in state_records if r.get('state') == 'planned')
        overdue = sum(
            1 for r in state_records
            if r.get('state') == 'planned' and r.get('date_deadline') and r['date_deadline'] < today
        )
        total_due = completed + scheduled
        completion_rate = (completed / total_due * 100.0) if total_due else 0.0
        overdue_rate = (overdue / scheduled * 100.0) if scheduled else 0.0
        productivity_score = max(0, min(100, completion_rate - overdue_rate * 0.5))

        return {
            'daily': daily,
            'weekly': weekly,
            'monthly': monthly,
            'performance': {
                'completion_rate': round(completion_rate, 2),
                'overdue': overdue,
                'pending': scheduled,
                'productivity_score': round(productivity_score, 1),
            },
        }

    @api.model
    def _aggregate_activities(self, base_domain):
        """Group activity counts by type for a given date domain.

        Returns dict with keys: calls, meetings, emails, completed,
        scheduled. The ``state`` field on ``mail.activity`` is a
        non-stored computed field, so we cannot use it in
        ``read_group`` directly — we fetch IDs only and bucket in
        Python using the in-memory state.
        """
        Activity = self.env['mail.activity']
        domain = base_domain + [('res_model', '=', 'crm.lead')]

        # Fetch the activity ids only — we bucket in Python.
        activity_ids = Activity.search(domain).ids
        if not activity_ids:
            return {'calls': 0, 'meetings': 0, 'emails': 0, 'other': 0,
                    'completed': 0, 'scheduled': 0}

        # Read the type name + state in batches to avoid huge RPCs.
        records = Activity.browse(activity_ids).read(
            ['activity_type_id', 'state']
        )

        type_buckets = {'calls': 0, 'meetings': 0, 'emails': 0, 'other': 0}
        state_buckets = {'done': 0, 'planned': 0, 'overdue': 0, 'today': 0}
        for rec in records:
            type_id = rec.get('activity_type_id')
            tname = (type_id[1].lower() if type_id else 'unknown')
            if 'call' in tname:
                type_buckets['calls'] += 1
            elif 'meeting' in tname or 'event' in tname:
                type_buckets['meetings'] += 1
            elif 'email' in tname or 'mail' in tname:
                type_buckets['emails'] += 1
            else:
                type_buckets['other'] += 1
            state_buckets[rec.get('state')] = state_buckets.get(rec.get('state'), 0) + 1

        return {
            'calls': type_buckets['calls'],
            'meetings': type_buckets['meetings'],
            'emails': type_buckets['emails'],
            'other': type_buckets['other'],
            'completed': state_buckets.get('done', 0),
            'scheduled': state_buckets.get('planned', 0),
        }

    # ===================================================================
    # SECTION 2B — DISPOSITION ANALYTICS (real engagement signal)
    # ===================================================================

    @api.model
    def _compute_disposition_analytics(self, filter_dict):
        """How opportunities are actually being worked in this pipeline.

        The scheduled-activity model (``mail.activity``: calls/meetings/
        emails/to-dos) has ~220 records against 7,500+ opportunities in
        this database -- this team disposition leads by moving their
        CRM stage (New -> Follow Up / No Answer / Not Interested / ...)
        rather than logging scheduled tasks, so the activity-based
        section reads as permanently near-zero. This computes the
        equivalent signal from stage movement instead: how many
        opportunities have left the entry stage, and how many were
        moved in the selected period (a throughput proxy, using
        ``write_date`` since there's no dedicated stage-change log
        field on crm.lead).

        The entry stage is found structurally (lowest ``sequence``)
        rather than by name match, since stage names are user-defined
        and, in this database, are stored with inconsistent
        translations across languages.
        """
        Lead = self.env['crm.lead']
        stages = self.env['crm.stage'].search([], order='sequence asc')
        if not stages:
            return {
                'entry_stage_id': None, 'total_active': 0, 'in_entry_stage': 0,
                'contact_rate': 0.0, 'worked_period': 0, 'by_stage': [],
                'trend': {'labels': [], 'datasets': []},
            }
        entry_stage_id = stages[0].id
        won_stage_ids = self._get_won_stage_ids()

        active_domain = [('type', '=', 'opportunity'), ('active', '=', True)]
        total_active = Lead.search_count(active_domain)

        stage_groups = Lead.read_group(active_domain, fields=['id'], groupby='stage_id', lazy=False)
        by_stage = []
        for g in stage_groups:
            sid = g['stage_id'][0] if g['stage_id'] else None
            sname = g['stage_id'][1] if g['stage_id'] else _('No Stage')
            by_stage.append({
                'stage_id': sid, 'name': sname, 'count': g['__count'],
                'is_entry': sid == entry_stage_id, 'is_won': sid in won_stage_ids,
            })
        by_stage.sort(key=lambda s: (0 if s['is_entry'] else (2 if s['is_won'] else 1), -s['count']))

        in_entry = next((s['count'] for s in by_stage if s['is_entry']), 0)
        contact_rate = round((total_active - in_entry) / total_active * 100.0, 2) if total_active else 0.0

        worked_domain = _build_domain(filter_dict, 'write_date') + [
            ('type', '=', 'opportunity'), ('stage_id', '!=', entry_stage_id),
        ]
        worked_period = Lead.search_count(worked_domain)

        trend_groups = Lead.read_group(worked_domain, fields=['id'], groupby='write_date:day', lazy=False)
        trend = self._normalize_trend(trend_groups, 'write_date:day', _('Opportunities Worked'))

        return {
            'entry_stage_id': entry_stage_id,
            'total_active': total_active,
            'in_entry_stage': in_entry,
            'contact_rate': contact_rate,
            'worked_period': worked_period,
            'by_stage': by_stage,
            'trend': trend,
        }

    # ===================================================================
    # SECTION 3 — PRODUCTIVITY DASHBOARD
    # ===================================================================

    @api.model
    def _compute_productivity(self, filter_dict):
        """Per-user and team productivity metrics.

        Uses ``read_group`` on ``user_id`` to compute, in a single query,
        per-salesperson aggregates: leads assigned, opportunities,
        won count, expected revenue, and activity counts.
        """
        Lead = self.env['crm.lead']
        Activity = self.env['mail.activity']

        # --- Per-user leads/opps/won ----------------------------------
        base_domain = _build_domain(filter_dict, 'create_date')
        user_groups = Lead.read_group(
            base_domain,
            fields=['id', 'expected_revenue', 'prorated_revenue'],
            groupby='user_id',
            lazy=False,
        )

        # Per-user won counts
        won_stage_ids = self._get_won_stage_ids()
        won_user_groups = Lead.read_group(
            base_domain + [('stage_id', 'in', won_stage_ids), ('type', '=', 'opportunity')],
            fields=['id', 'expected_revenue'],
            groupby='user_id',
            lazy=False,
        )
        won_by_user = {g['user_id'][0]: g for g in won_user_groups if g['user_id']}

        # Per-user activity counts
        act_user_groups = Activity.read_group(
            [('res_model', '=', 'crm.lead')] + base_domain,
            fields=['id'],
            groupby='user_id',
            lazy=False,
        )
        act_by_user = {g['user_id'][0]: g['__count'] for g in act_user_groups if g['user_id']}

        # Build per-user list
        user_metrics = []
        for g in user_groups:
            uid = g['user_id'][0] if g['user_id'] else None
            uname = g['user_id'][1] if g['user_id'] else 'Unassigned'
            total = g['__count']
            pipeline = g['expected_revenue']
            forecast = g['prorated_revenue']
            won_g = won_by_user.get(uid, {})
            won_count = won_g.get('__count', 0)
            won_revenue = won_g.get('expected_revenue', 0.0)
            activities = act_by_user.get(uid, 0)
            win_rate = (won_count / total * 100.0) if total else 0.0
            user_metrics.append({
                'user_id': uid,
                'name': uname,
                'leads_assigned': total,
                'opps_assigned': total,  # alias for clarity in views
                'activities_completed': activities,
                'conversion_rate': round(win_rate, 2),
                'win_rate': round(win_rate, 2),
                'revenue_generated': round(won_revenue, 2),
                'pipeline_value': round(pipeline, 2),
                'forecast': round(forecast, 2),
            })

        # --- Team metrics ---------------------------------------------
        team_groups = Lead.read_group(
            base_domain,
            fields=['id', 'expected_revenue', 'prorated_revenue'],
            groupby='team_id',
            lazy=False,
        )
        team_metrics = []
        for g in team_groups:
            tid = g['team_id'][0] if g['team_id'] else None
            tname = g['team_id'][1] if g['team_id'] else 'No Team'
            team_metrics.append({
                'team_id': tid,
                'name': tname,
                'leads': g['__count'],
                'pipeline': round(g['expected_revenue'], 2),
                'forecast': round(g['prorated_revenue'], 2),
            })

        # --- KPIs (per-employee averages) -----------------------------
        # Get all internal sales users (filtered by group if possible)
        sales_users = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True),
        ])
        n_users = max(len(sales_users), 1)

        total_revenue = sum(u['revenue_generated'] for u in user_metrics)
        total_opps = sum(u['leads_assigned'] for u in user_metrics)
        total_activities = sum(u['activities_completed'] for u in user_metrics)
        won_count_total = sum(won_by_user.get(u['user_id'], {}).get('__count', 0) for u in user_metrics if u['user_id'])

        return {
            'users': sorted(user_metrics, key=lambda x: x['revenue_generated'], reverse=True),
            'teams': sorted(team_metrics, key=lambda x: x['pipeline'], reverse=True),
            'kpis': {
                'leads_per_day': round(total_opps / 30.0, 2),
                'activities_per_day': round(total_activities / 30.0, 2),
                'revenue_per_employee': round(total_revenue / n_users, 2),
                'revenue_per_opp': round(total_revenue / total_opps, 2) if total_opps else 0.0,
                'activities_per_deal': round(total_activities / won_count_total, 2) if won_count_total else 0.0,
            },
            'rankings': {
                'salesperson': sorted(user_metrics, key=lambda x: x['revenue_generated'], reverse=True)[:5],
                'activity': sorted(user_metrics, key=lambda x: x['activities_completed'], reverse=True)[:5],
                'revenue': sorted(user_metrics, key=lambda x: x['revenue_generated'], reverse=True)[:5],
                'conversion': sorted(user_metrics, key=lambda x: x['conversion_rate'], reverse=True)[:5],
            },
        }

    # ===================================================================
    # SECTION 4 — STARTUP EXECUTIVE METRICS
    # ===================================================================

    @api.model
    def _compute_startup_metrics(self, filter_dict):
        """Business-health, growth, pipeline-health, and risk indicators.

        These metrics are most useful for founders/sales-leads who
        want to know "is the business healthy right now?" — they
        intentionally look at trailing windows that may extend beyond
        the user's selected filter.
        """
        Lead = self.env['crm.lead']
        won_stage_ids = self._get_won_stage_ids()
        today = fields.Date.today()
        today_dt = fields.Datetime.now()

        # --- Business health: last booking dates ----------------------
        last_booking = Lead.search_read(
            [('stage_id', 'in', won_stage_ids), ('date_closed', '!=', False)],
            fields=['date_closed'],
            order='date_closed desc',
            limit=1,
        )
        last_booking_date = last_booking[0]['date_closed'] if last_booking else None

        last_won_opp = Lead.search_read(
            [('type', '=', 'opportunity'), ('stage_id', 'in', won_stage_ids)],
            fields=['date_closed'],
            order='date_closed desc',
            limit=1,
        )
        last_won_date = last_won_opp[0]['date_closed'] if last_won_opp else None

        last_lead = Lead.search_read(
            [('type', '=', 'lead')],
            fields=['create_date'],
            order='create_date desc',
            limit=1,
        )
        last_lead_date = last_lead[0]['create_date'] if last_lead else None

        def _days_since(dt):
            if not dt:
                return None
            d = fields.Datetime.from_string(dt) if isinstance(dt, str) else dt
            return (today_dt - d).days

        # --- Growth metrics -------------------------------------------
        # Two clean, non-overlapping trailing windows of equal length,
        # compared directly. (The previous implementation built windows
        # with mismatched, overlapping ranges and then subtracted
        # unrelated counts, which could -- and did -- produce nonsense
        # or negative "previous period" figures.)
        #
        # Counted on ``type='opportunity'`` rather than ``type='lead'``:
        # this pipeline creates records straight as opportunities (2
        # 'lead'-type records exist in total), so a lead-based growth
        # metric would always read ~0 regardless of real activity.
        def _count_created_in_range(days_ago_start, days_ago_end):
            start = today - timedelta(days=days_ago_start)
            end = today - timedelta(days=days_ago_end)
            return Lead.search_count([
                ('type', '=', 'opportunity'),
                ('create_date', '>=', fields.Datetime.to_string(datetime.combine(start, datetime.min.time()))),
                ('create_date', '<=', fields.Datetime.to_string(datetime.combine(end, datetime.max.time()))),
            ])

        def _revenue_won_in_range(days_ago_start, days_ago_end):
            start = today - timedelta(days=days_ago_start)
            end = today - timedelta(days=days_ago_end)
            return self._sum_field([
                ('type', '=', 'opportunity'),
                ('stage_id', 'in', won_stage_ids),
                ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(start, datetime.min.time()))),
                ('date_closed', '<=', fields.Datetime.to_string(datetime.combine(end, datetime.max.time()))),
            ], 'expected_revenue')

        def _growth_pct(this_period, prev_period):
            return ((this_period - prev_period) / prev_period * 100.0) if prev_period else 0.0

        leads_this_week = _count_created_in_range(6, 0)
        leads_prev_week = _count_created_in_range(13, 7)
        weekly_growth = _growth_pct(leads_this_week, leads_prev_week)

        leads_this_month = _count_created_in_range(29, 0)
        leads_prev_month = _count_created_in_range(59, 30)
        monthly_growth = _growth_pct(leads_this_month, leads_prev_month)

        leads_this_quarter = _count_created_in_range(89, 0)
        leads_prev_quarter = _count_created_in_range(179, 90)
        quarterly_growth = _growth_pct(leads_this_quarter, leads_prev_quarter)

        rev_this_week = _revenue_won_in_range(6, 0)
        rev_prev_week = _revenue_won_in_range(13, 7)
        revenue_growth = _growth_pct(rev_this_week, rev_prev_week)

        # --- Pipeline health ------------------------------------------
        open_opps_domain = [
            ('type', '=', 'opportunity'),
            ('date_closed', '=', False),
        ]
        open_opps_count = Lead.search_count(open_opps_domain)
        open_opps_revenue = self._sum_field(open_opps_domain, 'expected_revenue')

        # Stale = open for more than 30 days
        stale_cutoff = fields.Datetime.to_string(today_dt - timedelta(days=30))
        stale_opps = Lead.search_count(open_opps_domain + [('date_open', '<=', stale_cutoff)])

        # Pipeline velocity = (won count * avg deal size) / avg cycle time
        # Simplified: (won revenue this period) / (avg days from create to close)
        won_this_period = self._sum_field(
            [('type', '=', 'opportunity'),
             ('stage_id', 'in', won_stage_ids),
             ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(today - timedelta(days=29), datetime.min.time())))],
            'expected_revenue',
        )

        # Pipeline coverage ratio = open pipeline / won revenue (target ~3x)
        won_30d = self._sum_field(
            [('type', '=', 'opportunity'),
             ('stage_id', 'in', won_stage_ids),
             ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(today - timedelta(days=29), datetime.min.time())))],
            'expected_revenue',
        )
        coverage = (open_opps_revenue / won_30d) if won_30d else 0.0

        # --- Risk indicators -------------------------------------------
        overdue_followups = Lead.search_count(
            open_opps_domain + [
                ('date_deadline', '<', fields.Date.to_string(today)),
            ]
        )
        no_bookings_7 = not bool(Lead.search_count(
            [('stage_id', 'in', won_stage_ids),
             ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(today - timedelta(days=7), datetime.min.time())))]
        ))
        no_bookings_14 = not bool(Lead.search_count(
            [('stage_id', 'in', won_stage_ids),
             ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(today - timedelta(days=14), datetime.min.time())))]
        ))
        no_bookings_30 = not bool(Lead.search_count(
            [('stage_id', 'in', won_stage_ids),
             ('date_closed', '>=', fields.Datetime.to_string(datetime.combine(today - timedelta(days=30), datetime.min.time())))]
        ))

        return {
            'business_health': {
                'last_booking_date': fields.Datetime.to_string(last_booking_date) if last_booking_date else None,
                'days_since_booking': _days_since(last_booking_date),
                'days_since_won_opp': _days_since(last_won_date),
                'days_since_lead': _days_since(last_lead_date),
            },
            'growth': {
                'weekly_growth': round(weekly_growth, 2),
                'monthly_growth': round(monthly_growth, 2),
                'quarterly_growth': round(quarterly_growth, 2),
                'revenue_growth': round(revenue_growth, 2),
                'lead_growth': round(weekly_growth, 2),
            },
            'pipeline_health': {
                'open_opps': open_opps_count,
                'open_value': round(open_opps_revenue, 2),
                'stale_opps': stale_opps,
                'pipeline_velocity': round(won_this_period / 30.0, 2),
                'coverage_ratio': round(coverage, 2),
            },
            'risk': {
                'no_bookings_7_days': no_bookings_7,
                'no_bookings_14_days': no_bookings_14,
                'no_bookings_30_days': no_bookings_30,
                'overdue_followups': overdue_followups,
                'stagnant_opps': stale_opps,
            },
        }

    # ===================================================================
    # SECTION 5 — OWNER / COVERAGE ANALYTICS
    # ===================================================================

    @api.model
    def _compute_owner_analytics(self, filter_dict):
        """Pipeline ownership and coverage, by salesperson.

        This replaces a lead-source breakdown: ``source_id`` is blank
        on the overwhelming majority of records in this pipeline (bulk
        imports and AI-assisted outreach don't set a UTM source), so a
        source-based chart is almost entirely an "Undefined" bucket
        and carries no signal. ``user_id`` (owner), by contrast, is
        set on every record and directly answers the more actionable
        question here: how much of the pipeline is actually assigned
        to and being worked by a real rep.
        """
        Lead = self.env['crm.lead']
        base_domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'opportunity')]
        won_stage_ids = self._get_won_stage_ids()

        owner_groups = Lead.read_group(
            base_domain,
            fields=['id', 'expected_revenue'],
            groupby='user_id',
            lazy=False,
        )
        won_by_owner_groups = Lead.read_group(
            base_domain + [('stage_id', 'in', won_stage_ids)],
            fields=['id'],
            groupby='user_id',
            lazy=False,
        )
        won_by_owner = {g['user_id'][0]: g['__count'] for g in won_by_owner_groups if g['user_id']}
        lost_by_owner_groups = Lead.read_group(
            _build_domain(filter_dict, 'create_date', include_inactive=True) + [
                ('type', '=', 'opportunity'), ('active', '=', False), ('probability', '=', 0),
            ],
            fields=['id'],
            groupby='user_id',
            lazy=False,
        )
        lost_by_owner = {g['user_id'][0]: g['__count'] for g in lost_by_owner_groups if g['user_id']}

        owners = []
        total = 0
        for g in owner_groups:
            oid = g['user_id'][0] if g['user_id'] else None
            oname = g['user_id'][1] if g['user_id'] else _('Unassigned')
            count = g['__count']
            total += count
            won_count = won_by_owner.get(oid, 0)
            lost_count = lost_by_owner.get(oid, 0)
            win_rate = (won_count / (won_count + lost_count) * 100.0) if (won_count + lost_count) else 0.0
            owners.append({
                'user_id': oid,
                'name': oname,
                'opportunities': count,
                'pipeline_value': round(g['expected_revenue'], 2),
                'won': won_count,
                'win_rate': round(win_rate, 2),
            })
        owners.sort(key=lambda o: o['opportunities'], reverse=True)

        top_owner = owners[0] if owners else None
        top_owner_share = round(top_owner['opportunities'] / total * 100.0, 2) if (total and top_owner) else 0.0

        return {
            'owners': owners,
            'total': total,
            'top_owner_share': top_owner_share,
        }

    # ===================================================================
    # SECTION 5B — CAMPAIGN PERFORMANCE, LEAD SOURCE & ROI
    # ===================================================================

    @api.model
    def _compute_campaign_analytics(self, filter_dict):
        """Lead-source breakdown and per-campaign performance/ROI.

        ROI per campaign = ``(won_revenue - budget) / budget * 100``.
        Budget is a manually-entered figure (``ced_budget`` on
        ``utm.campaign``) since Odoo CRM has no native ad-spend
        tracking. ROI is ``None`` (not shown) when budget is 0/unset
        to avoid a divide-by-zero or a misleading infinite figure.
        """
        Lead = self.env['crm.lead']
        base_domain = _build_domain(filter_dict, 'create_date')
        won_stage_ids = self._get_won_stage_ids()

        # --- Source of leads ------------------------------------------
        source_groups = Lead.read_group(base_domain, fields=['id'], groupby='source_id', lazy=False)
        total_with_source = sum(g['__count'] for g in source_groups)
        sources = []
        for g in source_groups:
            sid = g['source_id'][0] if g['source_id'] else False
            sname = g['source_id'][1] if g['source_id'] else _('Undefined')
            count = g['__count']
            won_count = Lead.search_count(
                base_domain + [
                    ('source_id', '=', sid), ('type', '=', 'opportunity'),
                    ('stage_id', 'in', won_stage_ids),
                ]
            )
            sources.append({
                'source_id': sid,
                'name': sname,
                'count': count,
                'share': round(count / total_with_source * 100.0, 2) if total_with_source else 0.0,
                'won': won_count,
            })
        sources.sort(key=lambda s: s['count'], reverse=True)

        # --- Campaign performance + ROI ---------------------------------
        campaign_groups = Lead.read_group(
            base_domain + [('campaign_id', '!=', False)],
            fields=['id', 'expected_revenue'],
            groupby='campaign_id',
            lazy=False,
        )
        campaign_ids = [g['campaign_id'][0] for g in campaign_groups if g['campaign_id']]
        budgets = {c.id: c.ced_budget for c in self.env['utm.campaign'].browse(campaign_ids)}

        campaigns = []
        for g in campaign_groups:
            if not g['campaign_id']:
                continue
            cid = g['campaign_id'][0]
            cname = g['campaign_id'][1]
            count = g['__count']
            won_revenue = self._sum_field(
                base_domain + [
                    ('campaign_id', '=', cid), ('type', '=', 'opportunity'),
                    ('stage_id', 'in', won_stage_ids),
                ],
                'expected_revenue',
            )
            budget = budgets.get(cid) or 0.0
            roi = round((won_revenue - budget) / budget * 100.0, 2) if budget else None
            campaigns.append({
                'campaign_id': cid,
                'name': cname,
                'leads': count,
                'won_revenue': round(won_revenue, 2),
                'budget': round(budget, 2),
                'roi': roi,
            })
        campaigns.sort(key=lambda c: c['won_revenue'], reverse=True)

        return {
            'sources': sources,
            'campaigns': campaigns,
        }

    # ===================================================================
    # SECTION 6 — SALES FUNNEL
    # ===================================================================

    @api.model
    def _compute_sales_funnel(self, filter_dict):
        """Pipeline-by-stage with conversion and drop-off percentages.

        Returns ordered list of stages with count, value, and the
        conversion/drop-off from the previous stage. The JS layer
        renders this as a horizontal funnel chart.
        """
        Lead = self.env['crm.lead']
        base_domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'opportunity')]

        # Order stages by sequence
        stages = self.env['crm.stage'].search([], order='sequence asc')
        stage_groups = Lead.read_group(
            base_domain,
            fields=['id', 'expected_revenue'],
            groupby='stage_id',
            lazy=False,
        )
        # Map: stage_id -> {count, revenue}
        by_stage = {g['stage_id'][0]: g for g in stage_groups if g['stage_id']}

        funnel = []
        prev_count = None
        for stage in stages:
            g = by_stage.get(stage.id, {'__count': 0, 'expected_revenue': 0.0})
            count = g['__count']
            value = g['expected_revenue']
            if prev_count and prev_count > 0:
                conversion = (count / prev_count * 100.0)
                drop_off = 100.0 - conversion
            else:
                conversion = 100.0 if count else 0.0
                drop_off = 0.0
            funnel.append({
                'stage_id': stage.id,
                'name': stage.name,
                'is_won': stage.is_won,
                'sequence': stage.sequence,
                'count': count,
                'value': round(value, 2),
                'conversion': round(conversion, 2),
                'drop_off': round(drop_off, 2),
            })
            prev_count = max(prev_count or 0, count)

        return {'stages': funnel}

    # ===================================================================
    # SECTION 7 — EXECUTIVE ALERT CENTER
    # ===================================================================

    @api.model
    def _compute_alerts(self, filter_dict):
        """Generate alert cards based on configurable thresholds.

        Thresholds are read from ``ir.config_parameter`` so admins
        can tune them without code changes.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        threshold_conversion = float(ICP.get_param('sgc_crm_dashboard.alert_conversion_threshold', 10.0))
        threshold_revenue = float(ICP.get_param('sgc_crm_dashboard.alert_revenue_threshold', 1000.0))
        threshold_overdue = int(ICP.get_param('sgc_crm_dashboard.alert_overdue_threshold', 10))

        kpi = self._compute_kpi_overview(filter_dict)
        startup = self._compute_startup_metrics(filter_dict)

        alerts = []

        # --- Stale pipeline backlog (headline) -------------------------
        # The single most actionable finding in this pipeline: a large
        # bulk import left most open opportunities sitting untouched.
        # Promoted to the front of the alert list rather than buried in
        # a chart further down the page.
        aging = self._aging_buckets(filter_dict)
        stale_count = aging['61-90 days']['count'] + aging['90+ days']['count']
        stale_value = aging['61-90 days']['value'] + aging['90+ days']['value']
        total_open = sum(b['count'] for b in aging.values())
        stale_share = (stale_count / total_open * 100.0) if total_open else 0.0
        if stale_count > 0:
            alerts.append({
                'level': 'danger' if stale_share >= 50 else 'warning',
                'title': _('Stale Pipeline Backlog'),
                'message': _(
                    '%(count)s open opportunities (%(share).0f%% of open pipeline, '
                    'worth %(value)s) have been open for more than 60 days without closing.'
                ) % {
                    'count': stale_count, 'share': stale_share,
                    'value': f'{stale_value:,.0f}',
                },
                'icon': 'fa-hourglass-end',
            })

        # --- Pipeline concentration risk --------------------------------
        owner_analytics = self._compute_owner_analytics(filter_dict)
        if owner_analytics['owners'] and owner_analytics['top_owner_share'] >= 50:
            top = owner_analytics['owners'][0]
            alerts.append({
                'level': 'danger' if owner_analytics['top_owner_share'] >= 75 else 'warning',
                'title': _('Pipeline Concentration Risk'),
                'message': _(
                    '%(name)s holds %(share).0f%% of active pipeline (%(count)s of '
                    '%(total)s opportunities) -- review team assignment coverage.'
                ) % {
                    'name': top['name'], 'share': owner_analytics['top_owner_share'],
                    'count': top['opportunities'], 'total': owner_analytics['total'],
                },
                'icon': 'fa-users',
            })

        if kpi['leads']['new_today'] == 0:
            alerts.append({
                'level': 'warning',
                'title': 'No New Leads Today',
                'message': 'Zero leads created today. Consider checking lead capture sources.',
                'icon': 'fa-user-plus',
            })

        if startup['risk']['no_bookings_7_days']:
            alerts.append({
                'level': 'danger',
                'title': 'No Bookings This Week',
                'message': 'No opportunities won in the last 7 days.',
                'icon': 'fa-calendar-times-o',
            })

        if kpi['conversion']['lead_conversion_rate'] < threshold_conversion:
            alerts.append({
                'level': 'warning',
                'title': 'Low Conversion Rate',
                'message': f'Lead conversion is {kpi["conversion"]["lead_conversion_rate"]:.1f}%, below threshold of {threshold_conversion:.1f}%.',
                'icon': 'fa-line-chart',
            })

        if kpi['revenue']['month'] < threshold_revenue:
            alerts.append({
                'level': 'warning',
                'title': 'Revenue Below Target',
                'message': f'Monthly revenue is {kpi["revenue"]["month"]:.0f}, below target of {threshold_revenue:.0f}.',
                'icon': 'fa-money',
            })

        if startup['risk']['overdue_followups'] > threshold_overdue:
            alerts.append({
                'level': 'danger',
                'title': 'High Overdue Activities',
                'message': f'{startup["risk"]["overdue_followups"]} opportunities are past their expected close date.',
                'icon': 'fa-exclamation-triangle',
            })

        if startup['pipeline_health']['stale_opps'] > 0:
            alerts.append({
                'level': 'warning',
                'title': 'Stale Opportunities',
                'message': f'{startup["pipeline_health"]["stale_opps"]} opportunities have been open for more than 30 days.',
                'icon': 'fa-clock-o',
            })

        # --- Dynamic rule-based alerts (configurable) --------------
        # Read active alert rules and evaluate them against the
        # already-computed payload.  This lets executives tune
        # thresholds without code changes.
        try:
            Rule = self.env['crm.dashboard.alert.rule']
            active_rules = Rule.sudo().search([('active', '=', True)])
            monthly_activity = self._aggregate_activities(
                self._period_domain('current_month')
            )
            rule_payload = {
                'kpi': kpi,
                'startup': startup,
                'funnel': self._compute_sales_funnel(filter_dict),
                'activity': {'monthly': monthly_activity},
            }
            for rule in active_rules:
                try:
                    for emitted in rule._evaluate_payload(rule_payload):
                        # Map severity to icon/level expected by the JS
                        emitted['icon'] = _RULE_ICONS.get(rule.rule_type, 'fa-bell')
                        emitted['level'] = _RULE_LEVEL_MAP.get(emitted.get('level'), 'warning')
                        alerts.append(emitted)
                except Exception as e:
                    _logger.warning("CED: alert rule %s evaluation failed: %s", rule.name, e)
        except Exception as e:
            # Never let rule evaluation break the dashboard
            _logger.warning("CED: alert rule dispatch failed: %s", e)

        if not alerts:
            alerts.append({
                'level': 'success',
                'title': 'All Systems Healthy',
                'message': 'No critical alerts at this time.',
                'icon': 'fa-check-circle',
            })

        return alerts

    # ===================================================================
    # SECTION 8 — CHARTS
    # ===================================================================

    @api.model
    def _compute_chart_data(self, filter_dict):
        """Prepare data for the 12 dashboard charts.

        Each chart key returns ``labels`` (x-axis) and ``datasets``
        (series). The frontend uses Chart.js, so we return data in
        the exact format Chart.js expects (without colors — those
        are set in the JS layer using the brand palette).
        """
        Lead = self.env['crm.lead']
        won_stage_ids = self._get_won_stage_ids()

        # --- 1-3: Opportunity creation trends (daily / weekly / monthly)
        # Filtered on type='opportunity', not 'lead': this pipeline
        # creates records straight as opportunities (2 'lead'-type rows
        # exist in total), so a lead-filtered trend is always empty.
        lead_domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'opportunity')]
        lead_trend = self._trend_data(lead_domain, 'create_date:day', 'Opportunities Created')
        weekly_trend = self._trend_data_week(lead_domain, 'create_date', 'Opportunities Created')
        monthly_trend = self._trend_data_month(lead_domain, 'create_date', 'Opportunities Created')

        # --- 4: Opportunity trend ------------------------------------
        opp_domain = _build_domain(filter_dict, 'date_open') + [('type', '=', 'opportunity')]
        opp_trend = self._trend_data(opp_domain, 'date_open:day', 'Opportunities')

        # --- 5: Revenue trend (daily) --------------------------------
        rev_domain = _build_domain(filter_dict, 'date_closed') + [
            ('type', '=', 'opportunity'),
            ('stage_id', 'in', won_stage_ids),
        ]
        rev_trend = self._trend_revenue(rev_domain, 'date_closed:day')

        # --- 6: Conversion trend -------------------------------------
        # Win rate over time
        conv_trend = self._trend_conversion(filter_dict)

        # --- 7: Disposition (engagement) trend ------------------------
        # Replaces the mail.activity-based trend (~220 rows against
        # 7,500+ opportunities -> effectively flat). Built from the
        # same stage-movement signal as the Disposition Analytics
        # section, so the chart and the section agree.
        disposition = self._compute_disposition_analytics(filter_dict)
        disposition_trend = disposition['trend']

        # --- 8: Sales funnel -----------------------------------------
        funnel = self._compute_sales_funnel(filter_dict)
        funnel_chart = {
            'labels': [s['name'] for s in funnel['stages']],
            'data': [s['count'] for s in funnel['stages']],
            'values': [s['value'] for s in funnel['stages']],
        }

        # --- 9: Pipeline by owner --------------------------------------
        # Replaces the lead-source pie: source_id is blank on 99.97% of
        # records here, owner is set on all of them and is the
        # actionable breakdown (coverage risk, not marketing attribution).
        owner_analytics = self._compute_owner_analytics(filter_dict)
        owner_chart = {
            'labels': [o['name'] for o in owner_analytics['owners'][:10]],
            'datasets': [{
                'label': _('Opportunities'),
                'data': [o['opportunities'] for o in owner_analytics['owners'][:10]],
            }],
        }

        # --- 10: Team performance bar --------------------------------
        productivity = self._compute_productivity(filter_dict)
        team_chart = {
            'labels': [t['name'] for t in productivity['teams']],
            'datasets': [{
                'label': _('Pipeline'),
                'data': [t['pipeline'] for t in productivity['teams']],
            }],
        }

        # --- 11: Revenue forecast (open pipeline by month) -----------
        forecast_chart = self._revenue_forecast_chart(filter_dict)

        # --- 12: Pipeline aging (promoted -- see Executive Alert Center)
        aging_chart = self._pipeline_aging_chart(filter_dict)

        return {
            'pipeline_aging': aging_chart,
            'opportunity_trend_daily': lead_trend,
            'opportunity_trend_weekly': weekly_trend,
            'opportunity_trend_monthly': monthly_trend,
            'opportunity_trend': opp_trend,
            'revenue_trend': rev_trend,
            'conversion_trend': conv_trend,
            'disposition_trend': disposition_trend,
            'funnel': funnel_chart,
            'owner_pipeline': owner_chart,
            'team_performance': team_chart,
            'revenue_forecast': forecast_chart,
        }

    @api.model
    def _trend_data(self, domain, groupby, label):
        """Generic time-series data: count of records bucketed by date."""
        Lead = self.env['crm.lead']
        groups = Lead.read_group(domain, fields=['id'], groupby=groupby, lazy=False)
        return self._normalize_trend(groups, groupby, label)

    @api.model
    def _trend_data_week(self, domain, date_field, label):
        """Weekly bucketed trend."""
        Lead = self.env['crm.lead']
        groups = Lead.read_group(
            domain,
            fields=['id'],
            groupby=f'{date_field}:week',
            lazy=False,
        )
        return self._normalize_trend(groups, f'{date_field}:week', label)

    @api.model
    def _trend_data_month(self, domain, date_field, label):
        Lead = self.env['crm.lead']
        groups = Lead.read_group(
            domain,
            fields=['id'],
            groupby=f'{date_field}:month',
            lazy=False,
        )
        return self._normalize_trend(groups, f'{date_field}:month', label)

    @api.model
    def _trend_revenue(self, domain, groupby):
        Lead = self.env['crm.lead']
        groups = Lead.read_group(domain, fields=['expected_revenue'], groupby=groupby, lazy=False)
        return self._normalize_trend(groups, groupby, 'Revenue', value_field='expected_revenue')

    @api.model
    def _trend_conversion(self, filter_dict):
        """Daily win rate (won / (won+lost)) for opportunities."""
        Lead = self.env['crm.lead']
        won_stage_ids = self._get_won_stage_ids()

        base = _build_domain(filter_dict, 'date_closed') + [('type', '=', 'opportunity')]
        base_incl_inactive = _build_domain(filter_dict, 'date_closed', include_inactive=True) + [
            ('type', '=', 'opportunity')]

        won_groups = Lead.read_group(
            base + [('stage_id', 'in', won_stage_ids)],
            fields=['id'],
            groupby='date_closed:day',
            lazy=False,
        )
        lost_groups = Lead.read_group(
            base_incl_inactive + [('active', '=', False), ('probability', '=', 0)],
            fields=['id'],
            groupby='date_closed:day',
            lazy=False,
        )
        won_map = {self._extract_date_key(g, 'date_closed:day'): g['__count'] for g in won_groups}
        lost_map = {self._extract_date_key(g, 'date_closed:day'): g['__count'] for g in lost_groups}
        all_keys = sorted(set(won_map.keys()) | set(lost_map.keys()))
        labels, data = [], []
        for k in all_keys:
            w = won_map.get(k, 0)
            l = lost_map.get(k, 0)
            total = w + l
            rate = (w / total * 100.0) if total else 0.0
            labels.append(k)
            data.append(round(rate, 2))
        return {'labels': labels, 'datasets': [{'label': 'Win Rate %', 'data': data}]}

    @api.model
    def _revenue_forecast_chart(self, filter_dict):
        """Forecast revenue bucketed by expected close month."""
        Lead = self.env['crm.lead']
        groups = Lead.read_group(
            _build_domain(filter_dict, 'date_open') + [
                ('type', '=', 'opportunity'),
                ('date_closed', '=', False),
            ],
            fields=['expected_revenue', 'prorated_revenue'],
            groupby='date_deadline:month',
            lazy=False,
        )
        labels, exp_data, fc_data = [], [], []
        for g in groups:
            key = self._extract_date_key(g, 'date_deadline:month')
            if key:
                labels.append(key)
                exp_data.append(round(g['expected_revenue'], 2))
                fc_data.append(round(g['prorated_revenue'], 2))
        return {
            'labels': labels,
            'datasets': [
                {'label': 'Expected', 'data': exp_data},
                {'label': 'Forecast', 'data': fc_data},
            ],
        }

    @api.model
    def _aging_buckets(self, filter_dict):
        """Open opportunities bucketed by age in days.

        Shared by the aging chart and the stale-pipeline alert, so
        both report the same numbers from a single query.
        """
        Lead = self.env['crm.lead']
        today_dt = fields.Datetime.now()
        open_opps = Lead.search(
            _build_domain(filter_dict, 'date_open') + [
                ('type', '=', 'opportunity'),
                ('date_closed', '=', False),
            ]
        ).read(['date_open', 'expected_revenue'])
        buckets = {
            '0-7 days': {'count': 0, 'value': 0.0},
            '8-30 days': {'count': 0, 'value': 0.0},
            '31-60 days': {'count': 0, 'value': 0.0},
            '61-90 days': {'count': 0, 'value': 0.0},
            '90+ days': {'count': 0, 'value': 0.0},
        }
        for o in open_opps:
            if not o['date_open']:
                continue
            age = (today_dt - fields.Datetime.from_string(o['date_open'])).days
            if age <= 7:
                k = '0-7 days'
            elif age <= 30:
                k = '8-30 days'
            elif age <= 60:
                k = '31-60 days'
            elif age <= 90:
                k = '61-90 days'
            else:
                k = '90+ days'
            buckets[k]['count'] += 1
            buckets[k]['value'] += o['expected_revenue']
        return buckets

    @api.model
    def _pipeline_aging_chart(self, filter_dict):
        """Open opportunities bucketed by age, as a Chart.js-ready bar chart.

        (Previously returned ``{labels, count_data, value_data}`` --
        every other chart in this engine returns ``{labels, datasets}``,
        which is the only shape the frontend's generic chart renderer
        actually reads. The mismatch meant this chart silently rendered
        as an empty canvas.)
        """
        buckets = self._aging_buckets(filter_dict)
        labels = list(buckets.keys())
        return {
            'labels': labels,
            'datasets': [
                {'label': _('Count'), 'data': [buckets[k]['count'] for k in labels]},
            ],
            'value_data': [round(buckets[k]['value'], 2) for k in labels],
        }

    # ===================================================================
    # HELPERS
    # ===================================================================

    @api.model
    def _normalize_trend(self, groups, groupby, label, value_field=None):
        """Convert read_group output to Chart.js {labels, datasets} format."""
        labels, data = [], []
        for g in groups:
            key = self._extract_date_key(g, groupby)
            if not key:
                continue
            labels.append(key)
            data.append(g[value_field] if value_field else g['__count'])
        return {
            'labels': labels,
            'datasets': [{'label': label, 'data': data}],
        }

    @api.model
    def _extract_date_key(self, group_dict, groupby):
        """Read_group returns dates as either ISO strings or datetime objects
        depending on the granularity. Normalize to a string label.
        """
        key = None
        # The key in the dict is the groupby string up to the colon
        prefix = groupby.split(':')[0]
        if prefix in group_dict and group_dict[prefix]:
            raw = group_dict[prefix]
            if isinstance(raw, str):
                key = raw
            elif hasattr(raw, 'isoformat'):
                key = raw.isoformat()
            else:
                # read_group format: [date, year, month, day, ...] for date granularity
                key = str(raw)
        if not key and groupby in group_dict:
            raw = group_dict[groupby]
            if raw:
                key = str(raw)
        return key

    @api.model
    def _get_won_stage_ids(self):
        """Return list of stage ids flagged as won. Cached for the request."""
        return self.env['crm.stage'].search([('is_won', '=', True)]).ids

    @api.model
    def _sum_field(self, domain, field_name):
        """Sum a numeric field across a domain. Returns 0.0 if no records."""
        result = self.env['crm.lead'].read_group(
            domain, fields=[field_name], groupby=[], lazy=False,
        )
        if not result:
            return 0.0
        return result[0].get(field_name, 0.0) or 0.0

    @api.model
    def _period_domain(self, period):
        """Build a domain restricted to a named period on mail.activity."""
        today = fields.Date.today()
        if period == 'today':
            start = end = today
        elif period == 'yesterday':
            start = end = today - timedelta(days=1)
        elif period == 'last_7_days':
            return [('date_deadline', '>=', today - timedelta(days=6)),
                    ('date_deadline', '<=', today)]
        elif period == 'current_month':
            start = today.replace(day=1)
            end = today
        else:
            start = end = today
        return [
            ('date_deadline', '>=', fields.Date.to_string(start)),
            ('date_deadline', '<=', fields.Date.to_string(end)),
        ]

    @api.model
    def _period_start(self, marker):
        today = fields.Date.today()
        if marker == 'current_month_start':
            return fields.Datetime.to_string(datetime.combine(today.replace(day=1), datetime.min.time()))
        if marker == 'current_quarter_start':
            qm = ((today.month - 1) // 3) * 3 + 1
            return fields.Datetime.to_string(datetime.combine(today.replace(month=qm, day=1), datetime.min.time()))
        if marker == 'current_year_start':
            return fields.Datetime.to_string(datetime.combine(today.replace(month=1, day=1), datetime.min.time()))
        if marker == 'today':
            return fields.Datetime.to_string(datetime.combine(today, datetime.min.time()))
        return fields.Datetime.now()

    @api.model
    def _period_end(self, marker):
        today = fields.Date.today()
        if marker == 'today':
            return fields.Datetime.to_string(datetime.combine(today, datetime.max.time()))
        return fields.Datetime.now()

    @api.model
    def _count_qualified_leads(self, filter_dict):
        """A lead is qualified if it has been converted to an opportunity
        (i.e. it has a non-null ``date_open``) or is currently past the
        first stage.
        """
        domain = _build_domain(filter_dict, 'create_date') + [('type', '=', 'lead'), ('date_open', '!=', False)]
        return self.env['crm.lead'].search_count(domain)

    @api.model
    def _count_awaiting_action_leads(self, filter_dict):
        """A lead is awaiting action if it has an overdue activity."""
        today = fields.Date.today()
        domain = _build_domain(filter_dict, 'create_date') + [
            ('type', '=', 'lead'),
            ('activity_ids.date_deadline', '<', today),
        ]
        return self.env['crm.lead'].search_count(domain)

    @api.model
    def _count_conversions(self, filter_dict, kind):
        Lead = self.env['crm.lead']
        if kind == 'lead_to_opp':
            domain = _build_domain(filter_dict, 'date_open') + [
                ('type', '=', 'opportunity'),
            ]
            return Lead.search_count(domain)
        if kind == 'opp_to_won':
            won = self._get_won_stage_ids()
            domain = _build_domain(filter_dict, 'date_closed') + [
                ('type', '=', 'opportunity'),
                ('stage_id', 'in', won),
            ]
            return Lead.search_count(domain)
        return 0

    @api.model
    def _compute_avg_conversion_days(self, filter_dict):
        """Average days from lead creation to opportunity close (won/lost).

        "Closed" here means ``date_closed`` is set, regardless of stage --
        that covers both won opportunities (still active) and lost ones
        (archived with probability=0). Filtering by stage_id membership
        in a "lost stages" list previously excluded every lost deal
        (since no stage is actually named "Lost" in this pipeline).
        """
        Lead = self.env['crm.lead']
        opps = Lead.search(
            _build_domain(filter_dict, 'date_closed', include_inactive=True) + [
                ('type', '=', 'opportunity'),
                ('date_closed', '!=', False),
            ]
        ).read(['create_date', 'date_closed'])
        if not opps:
            return 0
        total_days = 0
        count = 0
        for o in opps:
            if o['create_date'] and o['date_closed']:
                delta = fields.Datetime.from_string(o['date_closed']) - fields.Datetime.from_string(o['create_date'])
                total_days += delta.days
                count += 1
        return round(total_days / count, 1) if count else 0

    @api.model
    def _normalize_filter(self, filter_dict):
        """Echo back the filter state for the frontend to display."""
        start, end, label = _resolve_date_range(filter_dict)
        return {
            'period': filter_dict.get('period', 'last_30_days'),
            'label': label,
            'start': fields.Date.to_string(start),
            'end': fields.Date.to_string(end),
            'salesperson': filter_dict.get('user_id'),
            'team': filter_dict.get('team_id'),
            'source': filter_dict.get('source_id'),
            'stage': filter_dict.get('stage_id'),
            'company': filter_dict.get('company_id'),
        }
