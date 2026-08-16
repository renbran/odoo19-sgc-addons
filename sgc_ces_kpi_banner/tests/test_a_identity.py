# -*- coding: utf-8 -*-
"""Category A - CES identity, hr.version handling and manager resolution."""
from odoo import fields
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestCesIdentity(CesKpiCase):
    def test_ces_job_resolution_by_parameter(self):
        self.assertEqual(self.Identity._resolve_ces_job(), self.ces_job)

    def test_ces_job_resolution_by_name_when_id_missing(self):
        self.env["ir.config_parameter"].sudo().set_param("sgc_ces_kpi_banner.ces_job_id", "")
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.ces_job_name", self.ces_job.name
        )
        self.assertEqual(self.Identity._resolve_ces_job(), self.ces_job)

    def test_ces_job_resolution_survives_deleted_id(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.ces_job_id", "999999999"
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.ces_job_name", self.ces_job.name
        )
        self.assertEqual(self.Identity._resolve_ces_job(), self.ces_job)

    def test_is_ces_user(self):
        self.assertTrue(self.Identity.is_ces_user(self.ces_user))
        self.assertFalse(self.Identity.is_ces_user(self.other_user))

    def test_ces_employees_listing(self):
        self.assertIn(self.ces_employee, self.Identity.ces_employees())
        self.assertNotIn(self.other_employee, self.Identity.ces_employees())

    def test_current_version_is_latest_not_future(self):
        """MAX(date_version) <= today wins; future versions are ignored."""
        employee = self.ces_employee
        past = employee.version_id
        self.env["hr.version"].sudo().create(
            {
                "employee_id": employee.id,
                "date_version": fields.Date.to_date("2099-01-01"),
                "job_id": self.other_job.id,
            }
        )
        current = self.Identity._current_version(employee)
        self.assertEqual(current, past)
        self.assertEqual(current.job_id, self.ces_job)

    def test_multi_version_history_picks_most_recent_past(self):
        employee = self.ces_employee
        newer = self.env["hr.version"].sudo().create(
            {
                "employee_id": employee.id,
                "date_version": fields.Date.to_date("2026-03-01"),
                "job_id": self.ces_job.id,
            }
        )
        self.assertEqual(self.Identity._current_version(employee), newer)

    def test_ces_start_date_strategies(self):
        role_entry = self.Identity.ces_start_date(self.ces_employee, "role_entry")
        self.assertEqual(role_entry, fields.Date.to_date("2026-01-31"))
        self.assertTrue(self.Identity.ces_start_date(self.ces_employee, "create_date"))
        self.assertTrue(self.Identity.ces_start_date(self.ces_employee, "auto"))

    def test_manager_resolution_prefers_hr_responsible(self):
        self.assertEqual(
            self.Identity.resolve_manager(self.ces_employee), self.manager_user
        )

    def test_manager_resolution_reflects_a_change_of_responsible(self):
        other_manager = self.env["res.users"].create(
            {
                "name": "CES Second Manager",
                "login": "ces_test_manager_2",
                "email": "ces_test_manager_2@example.com",
                "group_ids": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.ces_employee.version_id.sudo().write({"hr_responsible_id": other_manager.id})
        self.assertEqual(self.Identity.resolve_manager(self.ces_employee), other_manager)

    def test_manager_resolution_returns_empty_for_no_employee(self):
        """The lower tiers of the hierarchy (parent_id, department manager,
        configured fallback) are defensive: in Odoo 19 hr.version.hr_responsible_id
        carries a NOT NULL constraint, so tier 1 practically always resolves.
        What must be guaranteed is that an unresolvable input never raises."""
        empty = self.env["hr.employee"].browse()
        self.assertFalse(self.Identity.resolve_manager(empty))
        self.assertFalse(self.Identity.resolve_manager_for_user(self.env["res.users"].browse()))

    def test_configured_fallback_parameter_is_readable(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.fallback_manager_uid", str(self.manager_user.id)
        )
        self.assertEqual(
            self.Identity._param_int("sgc_ces_kpi_banner.fallback_manager_uid"),
            self.manager_user.id,
        )

    def test_managed_user_ids(self):
        self.assertIn(
            self.ces_user.id, self.Identity.managed_user_ids(self.manager_user)
        )

    def test_no_hardcoded_stage_ids(self):
        """Stage resolution must go through config or name lookup only."""
        stage = self.env["crm.stage"].create({"name": "Test Proposal Stage"})
        self.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.proposal_stage_id", str(stage.id)
        )
        self.assertEqual(self.Identity.proposal_stage(), stage)
