# -*- coding: utf-8 -*-
from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_sales_playbook")
class TestLeadDistribution(TransactionCase):
    """Daily lead-distribution cron: SDR pool derivation (team members
    minus the team leader minus Administrator), fill-to-target allocation
    (not a flat +target for everyone), weekend skip, and dry-run safety."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_new = cls.env["crm.stage"].create(
            {"name": "Test New (distribution)", "sequence": 0}
        )
        cls.admin = cls.env.ref("base.user_admin")
        salesman_group = cls.env.ref("sales_team.group_sale_salesman")

        cls.leader = cls.env["res.users"].create({
            "name": "Test Team Leader",
            "login": "test_leader_dist",
            "email": "test_leader_dist@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })
        cls.sdr_a = cls.env["res.users"].create({
            "name": "Test SDR A",
            "login": "test_sdr_a_dist",
            "email": "test_sdr_a_dist@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })
        cls.sdr_b = cls.env["res.users"].create({
            "name": "Test SDR B",
            "login": "test_sdr_b_dist",
            "email": "test_sdr_b_dist@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })

        cls.team = cls.env["crm.team"].create({
            "name": "Test Distribution Team",
            "user_id": cls.leader.id,
        })
        cls.env["crm.team.member"].create([
            {"crm_team_id": cls.team.id, "user_id": cls.leader.id},
            {"crm_team_id": cls.team.id, "user_id": cls.sdr_a.id},
            {"crm_team_id": cls.team.id, "user_id": cls.sdr_b.id},
        ])

        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.lead_distribution_team_id", str(cls.team.id))
        ICP.set_param("sgc_sales_playbook.lead_distribution_stage_id", str(cls.stage_new.id))
        ICP.set_param("sgc_sales_playbook.lead_distribution_target_per_sdr", "3")

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Distribution Lead",
            "type": "opportunity",
            "stage_id": self.stage_new.id,
            "user_id": self.admin.id,
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _run_cron(self, on_date):
        with patch(
            "odoo.addons.sgc_sales_playbook.models.crm_lead.fields.Date.today",
            return_value=on_date,
        ):
            self.env["crm.lead"]._cron_daily_lead_distribution()

    def _new_stage_count(self, user):
        return self.env["crm.lead"].search_count(
            [("user_id", "=", user.id), ("stage_id", "=", self.stage_new.id)]
        )

    def test_sdr_pool_excludes_leader_and_administrator(self):
        pool = self.env["crm.lead"]._get_lead_distribution_sdr_users()
        self.assertIn(self.sdr_a, pool)
        self.assertIn(self.sdr_b, pool)
        self.assertNotIn(self.leader, pool, "Team leader must be excluded from the SDR pool")
        self.assertNotIn(self.admin, pool, "Administrator must be excluded from the SDR pool")

    def test_dry_run_does_not_reassign(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.lead_distribution_mode", "dry_run")
        for _ in range(5):
            self._make_lead()

        self._run_cron(date(2026, 8, 24))  # Monday

        self.assertEqual(self._new_stage_count(self.sdr_a), 0)
        self.assertEqual(self._new_stage_count(self.sdr_b), 0)
        attachment = self.env["ir.attachment"].search(
            [("name", "like", "sgc_lead_distribution_dry_run_%")], limit=1, order="id desc"
        )
        self.assertTrue(attachment, "Dry-run CSV attachment was not created")

    def test_live_fills_each_sdr_to_target_not_flat_add(self):
        """An SDR already at/above target gets 0 new leads this run; only
        the shortfall to the target is pulled from the source pool."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.lead_distribution_mode", "live")

        # sdr_a already at target (3) -> needs 0 more.
        for _ in range(3):
            self._make_lead(user_id=self.sdr_a.id)
        # sdr_b has 1 -> needs 2 more.
        self._make_lead(user_id=self.sdr_b.id)
        # Source pool under Administrator: 10, more than enough.
        for _ in range(10):
            self._make_lead()

        self._run_cron(date(2026, 8, 24))  # Monday

        self.assertEqual(
            self._new_stage_count(self.sdr_a), 3,
            "SDR already at target must not receive extra leads",
        )
        self.assertEqual(
            self._new_stage_count(self.sdr_b), 3,
            "SDR below target must be topped up to exactly the target",
        )

    def test_weekend_skips_entirely(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.lead_distribution_mode", "live")
        self._make_lead(user_id=self.sdr_b.id)
        for _ in range(5):
            self._make_lead()

        self._run_cron(date(2026, 8, 22))  # Saturday

        self.assertEqual(
            self._new_stage_count(self.sdr_b), 1,
            "A weekend run must not reassign anything",
        )
