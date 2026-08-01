# -*- coding: utf-8 -*-
# Part of SGC TECH AI. See LICENSE file for full copyright and licensing details.
# Copyright (c) 2026 SGC TECH AI (https://sgctech.ai)

"""Metadata-driven filter registry for SGC Dynamic Financial Reports.

This module is the single source of truth the enterprise filter bar (OWL)
reads to decide which filter widgets to render for a given ``report_type``.
Every ``wizard_field`` referenced below is a real field on
``sgc.financial.report.wizard`` (see ``sgc_financial_report_wizard.py``) —
nothing here is speculative. Fields not yet exposed as filters (e.g.
``schedule_name``) are intentionally left out of this registry.

Two registries:

* ``FILTER_DEFINITIONS`` — one entry per filter *key*, describing how to
  render it (widget type, label, which wizard field(s) it writes to) and
  where its option data comes from. Shared across every report.
* ``REPORT_METADATA`` — one entry per ``report_type``, declaring which
  filter keys apply, which are required, which sit in the primary
  single-row toolbar vs. the "More Filters" panel, and per-report smart
  defaults.

Nothing here hardcodes a filter *layout*; the OWL component walks
``toolbar_filters`` / ``more_filters`` in order and renders whatever
``FILTER_DEFINITIONS`` describes for each key.
"""

# ── Filter key -> widget/behavior definition ────────────────────────────
# widget values: "many2one", "many2many_tags", "date", "date_range",
#                "selection", "boolean"
FILTER_DEFINITIONS = {
    "company": {
        "label": "Company",
        "widget": "many2one",
        "wizard_field": "company_id",
        "model": "res.company",
        "searchable": True,
    },
    "date": {
        "label": "Date",
        "widget": "date_range",
        "wizard_field": ("date_from", "date_to"),
        "popup_calendar": True,
    },
    "compare": {
        "label": "Compare",
        "widget": "boolean_with_date_range",
        "wizard_field": "enable_comparison",
        "range_fields": ("comparison_date_from", "comparison_date_to"),
    },
    "journal": {
        "label": "Journal",
        "widget": "many2many_tags",
        "wizard_field": "journal_ids",
        "model": "account.journal",
        "searchable": True,
        "lazy_load": True,
        "domain": "[('company_id', '=', company_id)]",
    },
    "account": {
        "label": "Account",
        "widget": "many2many_tags",
        "wizard_field": "account_ids",
        "model": "account.account",
        "searchable": True,
        "lazy_load": True,
    },
    "account_group": {
        "label": "Account Group",
        "widget": "many2many_tags",
        "wizard_field": "account_group_ids",
        "model": "account.group",
        "searchable": True,
        "lazy_load": True,
    },
    "partner": {
        "label": "Partner",
        "widget": "many2many_tags",
        "wizard_field": "partner_ids",
        "model": "res.partner",
        "searchable": True,
        "lazy_load": True,
    },
    "partner_category": {
        "label": "Partner Tag",
        "widget": "many2one",
        "wizard_field": "partner_category_id",
        "model": "res.partner.category",
        "searchable": True,
    },
    "currency": {
        "label": "Currency",
        "widget": "many2one",
        "wizard_field": "currency_id",
        "model": "res.currency",
        "searchable": True,
    },
    "analytic": {
        "label": "Analytic Account",
        "widget": "many2many_tags",
        "wizard_field": "analytic_account_ids",
        "model": "account.analytic.account",
        "searchable": True,
        "lazy_load": True,
    },
    "analytic_breakdown": {
        "label": "Analytic Breakdown",
        "widget": "boolean",
        "wizard_field": "analytic_breakdown",
    },
    "target_move": {
        "label": "Move State",
        "widget": "selection",
        "wizard_field": "target_move",
        "options": [
            ("posted", "All Posted Entries"),
            ("all", "All Entries"),
            ("draft", "Draft Entries Only"),
        ],
    },
    "hierarchy": {
        "label": "Hierarchy",
        "widget": "boolean",
        "wizard_field": "show_hierarchy",
    },
    "hide_parent_hierarchy": {
        "label": "Hide Parent Hierarchy",
        "widget": "boolean",
        "wizard_field": "hide_parent_hierarchy",
    },
    "zero_balance": {
        "label": "Hide Zero",
        "widget": "boolean",
        "wizard_field": "show_zero_balance",
        "invert_display": True,
    },
    "budget": {
        "label": "Budget vs Actual",
        "widget": "boolean",
        "wizard_field": "show_budget_vs_actual",
    },
    "tax_grid": {
        "label": "Tax Grid Layout",
        "widget": "boolean",
        "wizard_field": "tax_grid",
    },
    "consolidate": {
        "label": "Consolidate Companies",
        "widget": "boolean_with_many2many",
        "wizard_field": "consolidate_companies",
        "range_fields": ("company_ids",),
    },
    # Aging buckets are a res.company setting (``sgc_dfr_aging_buckets``),
    # not a wizard field. Surfaced read-only so the OWL bar can show what
    # bucket ranges the aged reports will use, with a link to company
    # settings to change them — never a wizard-writable filter.
    "aging_buckets": {
        "label": "Aging Buckets",
        "widget": "readonly_company_setting",
        "company_field": "sgc_dfr_aging_buckets",
    },
}


def _toolbar(*keys):
    return list(keys)


# ── Per-report metadata ──────────────────────────────────────────────────
# toolbar_filters: rendered in the single horizontal enterprise toolbar row.
# more_filters: rendered only inside the "More Filters" advanced panel.
# required_filters: must have a value before Generate is enabled.
REPORT_METADATA = {
    "balance_sheet": {
        "label": "Balance Sheet",
        "toolbar_filters": _toolbar("company", "date", "compare", "currency", "journal"),
        "more_filters": ["account", "account_group", "analytic", "analytic_breakdown",
                          "target_move", "hierarchy", "hide_parent_hierarchy",
                          "zero_balance", "budget", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted", "zero_balance": False, "hierarchy": True},
        "comparison_support": True,
        "budget_support": True,
        "drilldown_support": True,
        "hierarchy_support": True,
        "export_types": ["xlsx", "pdf"],
    },
    "profit_loss": {
        "label": "Profit & Loss",
        "toolbar_filters": _toolbar("company", "date", "compare", "currency", "journal"),
        "more_filters": ["account", "account_group", "analytic", "analytic_breakdown",
                          "target_move", "hierarchy", "zero_balance", "budget", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted", "zero_balance": False, "hierarchy": True},
        "comparison_support": True,
        "budget_support": True,
        "drilldown_support": True,
        "hierarchy_support": True,
        "export_types": ["xlsx", "pdf"],
    },
    "cash_flow": {
        "label": "Cash Flow Statement",
        "toolbar_filters": _toolbar("company", "date", "compare", "currency"),
        "more_filters": ["journal", "account", "target_move", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted"},
        "comparison_support": True,
        "budget_support": False,
        "drilldown_support": False,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "trial_balance": {
        "label": "Trial Balance",
        "toolbar_filters": _toolbar("company", "date", "compare", "journal"),
        "more_filters": ["account", "account_group", "analytic", "target_move",
                          "hierarchy", "zero_balance", "budget", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted", "zero_balance": True},
        "comparison_support": True,
        "budget_support": True,
        "drilldown_support": True,
        "hierarchy_support": True,
        "export_types": ["xlsx", "pdf"],
    },
    "general_ledger": {
        "label": "General Ledger",
        "toolbar_filters": _toolbar("company", "date", "journal", "account", "partner"),
        "more_filters": ["currency", "analytic", "target_move", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted"},
        "comparison_support": False,
        "budget_support": False,
        "drilldown_support": True,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "partner_ledger": {
        "label": "Partner Ledger",
        "toolbar_filters": _toolbar("company", "partner", "date", "currency"),
        "more_filters": ["partner_category", "journal", "target_move", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"target_move": "posted"},
        "comparison_support": False,
        "budget_support": False,
        "drilldown_support": True,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "aged_receivable": {
        "label": "Aged Receivable",
        "toolbar_filters": _toolbar("company", "partner", "date"),
        "more_filters": ["partner_category", "aging_buckets", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {},
        "comparison_support": False,
        "budget_support": False,
        "drilldown_support": True,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "aged_payable": {
        "label": "Aged Payable",
        "toolbar_filters": _toolbar("company", "partner", "date"),
        "more_filters": ["partner_category", "aging_buckets", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {},
        "comparison_support": False,
        "budget_support": False,
        "drilldown_support": True,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "tax_report": {
        "label": "Tax Report",
        "toolbar_filters": _toolbar("company", "date"),
        "more_filters": ["tax_grid", "journal", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"tax_grid": False},
        "comparison_support": False,
        "budget_support": False,
        "drilldown_support": False,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
    "budget_vs_actual": {
        "label": "Budget vs Actual",
        "toolbar_filters": _toolbar("company", "date"),
        "more_filters": ["zero_balance", "consolidate"],
        "required_filters": ["company", "date"],
        "defaults": {"zero_balance": False},
        "comparison_support": False,
        "budget_support": True,
        "drilldown_support": False,
        "hierarchy_support": False,
        "export_types": ["xlsx", "pdf"],
    },
}


def get_report_metadata(report_type):
    """Return the metadata dict for ``report_type``, or ``None`` if unknown."""
    base = REPORT_METADATA.get(report_type)
    if base is None:
        return None
    return _with_smart_defaults(base)


def get_filter_definition(filter_key):
    """Return the shared widget/behavior definition for ``filter_key``."""
    return FILTER_DEFINITIONS.get(filter_key)


def get_full_registry():
    """Return the complete registry (all reports + all filter definitions).

    Shape consumed by the OWL enterprise filter bar on first load so it can
    cache filter widget definitions once and only re-fetch per-report
    metadata when ``report_type`` changes.

    Each report's ``defaults`` dict is augmented with computed values the
    static metadata cannot know about — current user's company, current
    fiscal-year start date, and today's date — so the Generate button is
    enabled out of the box.
    """
    return {
        "reports": {
            rtype: _with_smart_defaults(meta)
            for rtype, meta in REPORT_METADATA.items()
        },
        "filters": FILTER_DEFINITIONS,
    }


def _with_smart_defaults(meta):
    """Return a shallow copy of ``meta`` whose ``defaults`` includes the
    computed values that the static declaration cannot provide.
    Returns ``meta`` unchanged when called outside an HTTP context (no
    user/company available).
    """
    smart = _smart_defaults_for_current_user()
    if not smart:
        return meta
    out = dict(meta)
    out["defaults"] = {**meta.get("defaults", {}), **smart}
    return out


def _smart_defaults_for_current_user():
    """Compute Company (current user) and Date (calendar-year start -> today)
    smart defaults. Returns ``{}`` if no user/company is bound (e.g. module
    being loaded outside an HTTP request).
    """
    from odoo import fields
    from odoo.http import request

    smart = {}
    try:
        if request is None or not getattr(request, "env", None):
            return smart
        user = request.env.user
    except Exception:
        return smart

    if not user or not user.company_id:
        return smart

    today = fields.Date.today()
    # Conservative: start of calendar year. Real fiscal-year alignment would
    # need per-company fiscalyear config; keeping it predictable for the pilot.
    fy_start = today.replace(month=1, day=1)

    smart["company"] = user.company_id.id
    smart["date"] = [fy_start.isoformat(), today.isoformat()]
    return smart
