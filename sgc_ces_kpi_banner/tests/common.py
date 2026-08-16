# -*- coding: utf-8 -*-
"""Shared fixtures. Every test builds its own job, employees, users and leads,
so the suite never depends on the contents of the target database."""
from odoo import fields
from odoo.tests.common import TransactionCase


class CesKpiCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Identity = cls.env["sgc.ces.identity"]
        cls.Registry = cls.env["sgc.ces.metric.registry"]
        cls.Service = cls.env["sgc.ces.kpi.service"]

        cls.ces_job = cls.env["hr.job"].create({"name": "CES Test Role"})
        cls.other_job = cls.env["hr.job"].create({"name": "Other Test Role"})
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.ces_job_id", str(cls.ces_job.id)
        )

        # Ensure the test runner is in the administrator group so admin-only
        # assertions do not require an extra sudo() dance.
        cls.env.user.write({
            "groups_id": [
                (4, cls.env.ref("base.group_user").id),
                (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_admin").id),
            ],
        })

        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "CES Test Manager",
                "login": "ces_test_manager",
                "email": "ces_test_manager@example.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_manager").id),
                    (4, cls.env.ref("sales_team.group_sale_salesman").id),
                ],
            }
        )
        cls.ces_user = cls.env["res.users"].create(
            {
                "name": "CES Test Rep",
                "login": "ces_test_rep",
                "email": "ces_test_rep@example.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_user").id),
                    (4, cls.env.ref("sales_team.group_sale_salesman").id),
                ],
            }
        )
        cls.other_user = cls.env["res.users"].create(
            {
                "name": "Non CES Test User",
                "login": "ces_test_other",
                "email": "ces_test_other@example.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_user").id),
                ],
            }
        )

        cls.manager_employee = cls.env["hr.employee"].create(
            {"name": "CES Test Manager", "user_id": cls.manager_user.id}
        )
        cls.ces_employee = cls.env["hr.employee"].create(
            {
                "name": "CES Test Rep",
                "user_id": cls.ces_user.id,
                "job_id": cls.ces_job.id,
                "hr_responsible_id": cls.manager_user.id,
            }
        )
        cls.other_employee = cls.env["hr.employee"].create(
            {
                "name": "Non CES Test User",
                "user_id": cls.other_user.id,
                "job_id": cls.other_job.id,
            }
        )
        # Deterministic anchor for every scheduling assertion.
        cls.ces_employee.version_id.sudo().write({"date_version": fields.Date.to_date("2026-01-31")})

    # -- helpers -------------------------------------------------------------
    @classmethod
    def _make_plan(cls, **overrides):
        values = {
            "name": "Test Plan",
            "code": "test_plan_%s" % cls.env.cr.dbname[:6],
            "is_default": True,
            "start_date_strategy": "role_entry",
        }
        values.update(overrides)
        return cls.env["sgc.ces.gate.plan"].create(values)

    @classmethod
    def _make_template(cls, plan, **overrides):
        values = {
            "plan_id": plan.id,
            "name": "Gate T",
            "code": "gate_t",
            "offset_months": 0,
            "duration_months": 1,
            "review_lead_days": 7,
        }
        values.update(overrides)
        return cls.env["sgc.ces.gate.template"].create(values)

    @classmethod
    def _make_requirement(cls, template, **overrides):
        values = {
            "template_id": template.id,
            "name": "Pipeline",
            "metric_code": "pipeline_qualified_value",
            "comparator": ">=",
            "target_value": 1000.0,
            "measurement_window": "all_time",
            "level": "mandatory",
        }
        values.update(overrides)
        return cls.env["sgc.ces.gate.requirement"].create(values)

    @classmethod
    def _make_assignment(cls, plan, employee=None, activate=True):
        assignment = cls.env["sgc.ces.gate.assignment"].create(
            {
                "employee_id": (employee or cls.ces_employee).id,
                "plan_id": plan.id,
                "start_date": fields.Date.to_date("2026-01-31"),
            }
        )
        if activate:
            assignment.action_activate()
        return assignment

    @classmethod
    def _make_lead(cls, user, revenue=1000.0, stage=None, last_stage_update=None):
        lead = cls.env["crm.lead"].create(
            {
                "name": "Test Opportunity",
                "type": "opportunity",
                "user_id": user.id,
                "expected_revenue": revenue,
                "stage_id": stage.id if stage else False,
            }
        )
        if last_stage_update:
            # The ORM may not have flushed the INSERT yet; force it so the raw
            # UPDATE below is not overwritten.
            cls.env.flush_all()
            cls.env.cr.execute(
                "UPDATE crm_lead SET date_last_stage_update = %s WHERE id = %s",
                (last_stage_update, lead.id),
            )
            lead.invalidate_recordset(["date_last_stage_update"])
        return lead
