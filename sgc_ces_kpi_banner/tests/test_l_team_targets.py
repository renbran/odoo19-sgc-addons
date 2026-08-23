# -*- coding: utf-8 -*-
"""Category L - sales-team scoped targets, Team Leader access, weekday-only
targets and the New-stage-exit metric. Everyone here is a plain salesperson,
not a CES employee, to prove the framework no longer requires the CES job."""
from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged

from .common import CesKpiCase


@tagged("post_install", "-at_install", "sgc_ces_kpi_banner")
class TestTeamTargets(CesKpiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.leader_user = cls.env["res.users"].create(
            {
                "name": "Team Leader",
                "login": "ces_test_leader",
                "email": "ces_test_leader@example.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_manager").id),
                    (4, cls.env.ref("sales_team.group_sale_salesman").id),
                ],
            }
        )
        cls.rep_a = cls.env["res.users"].create(
            {
                "name": "Team Rep A",
                "login": "ces_test_rep_a",
                "email": "ces_test_rep_a@example.com",
                "group_ids": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("sgc_ces_kpi_banner.group_ces_kpi_user").id),
                    (4, cls.env.ref("sales_team.group_sale_salesman").id),
                ],
            }
        )
        cls.team = cls.env["crm.team"].create(
            {
                "name": "Test Sales Team",
                "user_id": cls.leader_user.id,
                "member_ids": [(6, 0, [cls.rep_a.id])],
            }
        )
        cls.other_team = cls.env["crm.team"].create({"name": "Other Test Team"})
        cls.new_stage = cls.env["crm.stage"].create({"name": "New", "sequence": 0})
        cls.mid_stage = cls.env["crm.stage"].create({"name": "Qualified", "sequence": 1})
        cls.env["ir.config_parameter"].sudo().set_param(
            "sgc_ces_kpi_banner.new_stage_id", str(cls.new_stage.id)
        )

    # -- identity: team leadership --------------------------------------
    def test_led_team_member_ids(self):
        self.assertEqual(
            set(self.Identity.led_team_member_ids(self.leader_user)), {self.rep_a.id}
        )
        self.assertFalse(self.Identity.led_team_member_ids(self.rep_a))

    def test_managed_user_ids_includes_led_team(self):
        self.assertIn(self.rep_a.id, self.Identity.managed_user_ids(self.leader_user))

    def test_leader_can_read_team_member_summary(self):
        summary = self.Service.with_user(self.leader_user).get_ces_kpi_summary(self.rep_a.id)
        self.assertEqual(summary["user_id"], self.rep_a.id)

    def test_leader_cannot_read_other_teams_member(self):
        outsider = self.other_user
        with self.assertRaises(AccessError):
            self.Service.with_user(self.leader_user).get_ces_kpi_summary(outsider.id)

    # -- new-stage-exit metric --------------------------------------------
    def test_new_stage_exit_counts_only_leads_that_left_new(self):
        today = date.today()
        self._make_lead(self.rep_a, stage=self.mid_stage, last_stage_update=today)
        self._make_lead(self.rep_a, stage=self.new_stage, last_stage_update=today)
        outcome = self.Registry.evaluate(
            "pipeline_new_stage_exit_count",
            {"user_id": self.rep_a.id, "date_from": today, "date_to": today, "params": {}},
        )
        self.assertEqual(outcome["value"], 1.0)

    def test_new_stage_exit_ignores_changes_outside_window(self):
        yesterday = date.today() - timedelta(days=1)
        self._make_lead(self.rep_a, stage=self.mid_stage, last_stage_update=yesterday)
        outcome = self.Registry.evaluate(
            "pipeline_new_stage_exit_count",
            {
                "user_id": self.rep_a.id,
                "date_from": date.today(),
                "date_to": date.today(),
                "params": {},
            },
        )
        self.assertEqual(outcome["value"], 0.0)

    # -- team-scoped applicability -----------------------------------------
    def test_team_target_applies_to_members_and_leader(self):
        target = self.env["sgc.ces.kpi.target"].create(
            {
                "name": "Team quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
                "team_id": self.team.id,
            }
        )
        self.assertIn(target, self.env["sgc.ces.kpi.target"].targets_for_user(self.rep_a, "daily"))
        self.assertIn(
            target, self.env["sgc.ces.kpi.target"].targets_for_user(self.leader_user, "daily")
        )
        self.assertNotIn(
            target, self.env["sgc.ces.kpi.target"].targets_for_user(self.other_user, "daily")
        )

    def test_user_specific_target_beats_team_target(self):
        Target = self.env["sgc.ces.kpi.target"]
        Target.create(
            {
                "name": "Team quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
                "team_id": self.team.id,
            }
        )
        personal = Target.create(
            {
                "name": "Personal quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 80.0,
                "period": "daily",
                "team_id": self.team.id,
                "user_id": self.rep_a.id,
            }
        )
        resolved = Target.targets_for_user(self.rep_a, "daily")
        self.assertEqual(resolved.mapped("id"), personal.ids)

    def test_team_scope_rejects_user_outside_team(self):
        with self.assertRaises(ValidationError):
            self.env["sgc.ces.kpi.target"].create(
                {
                    "name": "Bad scope",
                    "metric_code": "pipeline_new_stage_exit_count",
                    "target_value": 60.0,
                    "period": "daily",
                    "team_id": self.team.id,
                    "user_id": self.other_user.id,
                }
            )

    # -- weekdays_only -------------------------------------------------------
    def test_weekdays_only_target_hidden_on_weekend_shown_on_weekday(self):
        Target = self.env["sgc.ces.kpi.target"]
        target = Target.create(
            {
                "name": "Weekday quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
                "team_id": self.team.id,
                "weekdays_only": True,
            }
        )
        saturday = date(2026, 8, 22)
        monday = date(2026, 8, 24)
        self.assertEqual(saturday.weekday(), 5)
        self.assertEqual(monday.weekday(), 0)
        self.assertNotIn(
            target, Target.targets_for_user(self.rep_a, "daily", reference=saturday)
        )
        self.assertIn(target, Target.targets_for_user(self.rep_a, "daily", reference=monday))

    def test_non_weekdays_only_target_shown_every_day(self):
        Target = self.env["sgc.ces.kpi.target"]
        target = Target.create(
            {
                "name": "Any-day quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
                "team_id": self.team.id,
            }
        )
        saturday = date(2026, 8, 22)
        self.assertIn(target, Target.targets_for_user(self.rep_a, "daily", reference=saturday))

    # -- security: Team Leader defines targets for their own team only -----
    def test_leader_can_create_target_for_own_team(self):
        target = self.env["sgc.ces.kpi.target"].with_user(self.leader_user).create(
            {
                "name": "Leader-defined quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
                "team_id": self.team.id,
            }
        )
        self.assertEqual(target.team_id, self.team)

    def test_leader_cannot_create_target_for_another_team(self):
        with self.assertRaises(AccessError):
            self.env["sgc.ces.kpi.target"].with_user(self.leader_user).create(
                {
                    "name": "Rogue quota",
                    "metric_code": "pipeline_new_stage_exit_count",
                    "target_value": 60.0,
                    "period": "daily",
                    "team_id": self.other_team.id,
                }
            )

    def test_leader_cannot_create_company_wide_target(self):
        with self.assertRaises(AccessError):
            self.env["sgc.ces.kpi.target"].with_user(self.leader_user).create(
                {
                    "name": "Rogue company-wide quota",
                    "metric_code": "pipeline_new_stage_exit_count",
                    "target_value": 60.0,
                    "period": "daily",
                }
            )

    def test_leader_can_still_read_company_wide_targets(self):
        company_wide = self.env["sgc.ces.kpi.target"].sudo().create(
            {
                "name": "Company wide quota",
                "metric_code": "pipeline_new_stage_exit_count",
                "target_value": 60.0,
                "period": "daily",
            }
        )
        visible = (
            self.env["sgc.ces.kpi.target"]
            .with_user(self.leader_user)
            .search([("id", "=", company_wide.id)])
        )
        self.assertTrue(visible)
