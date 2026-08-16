# -*- coding: utf-8 -*-
{
    "name": "SGC - CES KPI & Gate Banner",
    "version": "19.0.1.0.0",
    "category": "CRM",
    "summary": "Floating CES KPI banner, configurable gate plans, manager review workflow",
    "description": """
SGC CES KPI & Gate Banner
=========================
Gives Customer Engagement Specialists (CES) a floating, collapsible KPI
banner in the Odoo backend showing their current gate progress, daily and
monthly KPI targets, and a deterministic "next recommended action".

Everything is configuration, not code:

* ``sgc.ces.gate.plan``        - versioned plan; one active default plan per company, no routing
* ``sgc.ces.gate.template``    - per-gate schedule and policy
* ``sgc.ces.gate.requirement`` - generic metric + comparator + target
* ``sgc.ces.gate.assignment``  - employee to plan binding
* ``sgc.ces.gate.instance``    - snapshotted per-employee gate occurrence
* ``sgc.ces.gate.review``      - manager review workflow
* ``sgc.ces.gate.consideration`` - additive extensions / target adjustments

Metrics are dispatched by explicit ``metric_code`` string lookup in
``models/metric_registry.py``. No ``eval``, no ``exec``, no domains or SQL
are ever stored in configuration records and executed later.

v1 is informational only: it never blocks a CRM write, a stage change or a
login, never sends email by default, and never auto-activates an employee
assignment on install.
    """,
    "author": "SGC Tech AI",
    "website": "https://sgctech.ai",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "mail",
        "crm",
        "sales_team",
        "sale_management",
        "sale_crm",
        "account",
        "hr",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/default_config.xml",
        "data/mail_activity_data.xml",
        "data/gate_plan_data.xml",
        "data/ir_cron.xml",
        "views/wizard_views.xml",
        "views/gate_plan_views.xml",
        "views/gate_template_views.xml",
        "views/gate_requirement_views.xml",
        "views/gate_assignment_views.xml",
        "views/baseline_assessment_views.xml",
        "views/gate_instance_views.xml",
        "views/gate_review_views.xml",
        "views/gate_consideration_views.xml",
        "views/kpi_target_views.xml",
        "views/res_config_settings_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sgc_ces_kpi_banner/static/src/services/ces_kpi_service.js",
            "sgc_ces_kpi_banner/static/src/components/ces_kpi_banner/ces_kpi_banner.scss",
            "sgc_ces_kpi_banner/static/src/components/ces_kpi_banner/ces_kpi_banner.js",
            "sgc_ces_kpi_banner/static/src/components/ces_kpi_banner/ces_kpi_banner.xml",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
