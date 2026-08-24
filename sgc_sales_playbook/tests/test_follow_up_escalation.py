# -*- coding: utf-8 -*-
from datetime import date, datetime
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_sales_playbook")
class TestFollowUpEscalation(TransactionCase):
    """3-step Follow Up stage discipline: day 2+ notification, day 4+
    final warning, day 5+ random redistribution (excluding the current
    owner) back to New — all counted in BUSINESS days, all defaulting to
    dry-run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_follow_up = cls.env["crm.stage"].create(
            {"name": "Test Follow Up (escalation)", "sequence": 5}
        )
        cls.stage_new = cls.env["crm.stage"].create(
            {"name": "Test New (escalation)", "sequence": 0}
        )
        salesman_group = cls.env.ref("sales_team.group_sale_salesman")

        cls.leader = cls.env["res.users"].create({
            "name": "Test Escalation Leader",
            "login": "test_leader_escalation",
            "email": "test_leader_escalation@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })
        cls.sdr_a = cls.env["res.users"].create({
            "name": "Test Escalation SDR A",
            "login": "test_sdr_a_escalation",
            "email": "test_sdr_a_escalation@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })
        cls.sdr_b = cls.env["res.users"].create({
            "name": "Test Escalation SDR B",
            "login": "test_sdr_b_escalation",
            "email": "test_sdr_b_escalation@example.com",
            "group_ids": [(6, 0, [salesman_group.id])],
        })

        cls.team = cls.env["crm.team"].create({
            "name": "Test Escalation Team",
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
        ICP.set_param("sgc_sales_playbook.follow_up_stage_id", str(cls.stage_follow_up.id))
        ICP.set_param("sgc_sales_playbook.follow_up_escalation_mode", "live")

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Escalation Lead",
            "type": "opportunity",
            "stage_id": self.stage_follow_up.id,
            "user_id": self.sdr_a.id,
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _set_stage_entry(self, lead, dt):
        """Raw-SQL backdate of date_last_stage_update to an exact
        datetime — same flush-before-write gotcha as
        test_dead_lead_cleanup.py's _backdate (the ORM's own pending
        "now" would otherwise silently overwrite this on the next
        flush)."""
        lead.flush_recordset()
        self.env.cr.execute(
            "UPDATE crm_lead SET date_last_stage_update=%s WHERE id=%s",
            (fields.Datetime.to_string(dt), lead.id),
        )
        lead.invalidate_recordset()

    def _run_cron(self, on_date):
        with patch(
            "odoo.addons.sgc_sales_playbook.models.crm_lead.fields.Date.today",
            return_value=on_date,
        ):
            self.env["crm.lead"]._cron_follow_up_stage_escalation()

    def _activity_count(self, lead, summary):
        return self.env["mail.activity"].search_count([
            ("res_model", "=", "crm.lead"),
            ("res_id", "=", lead.id),
            ("summary", "=", summary),
        ])

    # ── _business_days_elapsed ───────────────────────────────────────────

    def test_business_days_elapsed_skips_weekend(self):
        model = self.env["crm.lead"]
        # Thu 2026-08-20 -> Mon 2026-08-24: Fri counts, Sat/Sun don't.
        self.assertEqual(
            model._business_days_elapsed(datetime(2026, 8, 20, 9, 0), date(2026, 8, 24)),
            2,
        )
        # Thu 2026-08-20 -> Thu 2026-08-27: full business week.
        self.assertEqual(
            model._business_days_elapsed(datetime(2026, 8, 20, 9, 0), date(2026, 8, 27)),
            5,
        )

    # ── day 2 ─────────────────────────────────────────────────────────────

    def test_day2_sends_notification_and_is_idempotent(self):
        lead = self._make_lead()
        self._set_stage_entry(lead, datetime(2026, 8, 25, 9, 0))  # elapsed=2 by Aug 27

        self._run_cron(date(2026, 8, 27))  # Thursday

        self.assertEqual(
            self._activity_count(lead, "Follow Up Stalled: Day 2 Notification"), 1
        )
        mail = self.env["mail.mail"].search(
            [("email_to", "=", self.sdr_a.email)], limit=1, order="id desc"
        )
        self.assertTrue(mail, "Day-2 email was not created")
        # Stage/owner must be untouched at day 2.
        self.assertEqual(lead.stage_id, self.stage_follow_up)
        self.assertEqual(lead.user_id, self.sdr_a)

        # Re-running the same day (or a later one still < day 4) must not
        # create a second activity/email.
        self._run_cron(date(2026, 8, 27))
        self.assertEqual(
            self._activity_count(lead, "Follow Up Stalled: Day 2 Notification"), 1
        )

    # ── day 4 ─────────────────────────────────────────────────────────────

    def test_day4_sends_final_warning(self):
        lead = self._make_lead()
        self._set_stage_entry(lead, datetime(2026, 8, 21, 9, 0))  # elapsed=4 by Aug 27

        self._run_cron(date(2026, 8, 27))  # Thursday

        self.assertEqual(
            self._activity_count(lead, "Follow Up Stalled: Day 4 Final Warning"), 1
        )
        self.assertEqual(lead.stage_id, self.stage_follow_up)
        self.assertEqual(lead.user_id, self.sdr_a)

    # ── day 5 ─────────────────────────────────────────────────────────────

    def test_day5_redistributes_excluding_current_owner_and_resets_stage(self):
        lead = self._make_lead(user_id=self.sdr_a.id)
        self._set_stage_entry(lead, datetime(2026, 8, 20, 9, 0))  # elapsed=5 by Aug 27

        self._run_cron(date(2026, 8, 27))  # Thursday

        self.assertEqual(lead.stage_id, self.stage_new)
        self.assertNotEqual(
            lead.user_id, self.sdr_a, "Current owner must not receive the lead back"
        )
        # sdr_b is the only other eligible SDR (leader + Administrator are
        # structurally excluded), so the random pick is deterministic here.
        self.assertEqual(lead.user_id, self.sdr_b)

    # ── dry run / weekend safety ─────────────────────────────────────────

    def test_dry_run_makes_no_changes(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.follow_up_escalation_mode", "dry_run")

        lead = self._make_lead(user_id=self.sdr_a.id)
        self._set_stage_entry(lead, datetime(2026, 8, 20, 9, 0))  # elapsed=5

        self._run_cron(date(2026, 8, 27))

        self.assertEqual(lead.stage_id, self.stage_follow_up)
        self.assertEqual(lead.user_id, self.sdr_a)
        self.assertEqual(
            self._activity_count(lead, "Follow Up Stalled: Day 2 Notification"), 0
        )
        attachment = self.env["ir.attachment"].search(
            [("name", "like", "sgc_follow_up_escalation_dry_run_%")], limit=1, order="id desc"
        )
        self.assertTrue(attachment, "Dry-run CSV attachment was not created")

    def test_weekend_skips_entirely(self):
        lead = self._make_lead(user_id=self.sdr_a.id)
        self._set_stage_entry(lead, datetime(2026, 8, 20, 9, 0))  # would be elapsed=5

        self._run_cron(date(2026, 8, 22))  # Saturday

        self.assertEqual(lead.stage_id, self.stage_follow_up)
        self.assertEqual(lead.user_id, self.sdr_a)
