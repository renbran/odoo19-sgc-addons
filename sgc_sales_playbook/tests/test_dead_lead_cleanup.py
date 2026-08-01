# -*- coding: utf-8 -*-
import base64
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_sales_playbook")
class TestDeadLeadCleanup(TransactionCase):
    """B4 regression: dry-run selects the expected fixture set and touches
    nothing; live mode archives correctly and is idempotent on a second
    run."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage_meeting = cls.env["crm.stage"].create(
            {"name": "Test Meeting Booked (cleanup)", "sequence": 7}
        )
        cls.stage_dead_end = cls.env["crm.stage"].create(
            {"name": "Test Dead End (cleanup)", "sequence": 10}
        )
        ICP = cls.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_end_stage_ids", str(cls.stage_dead_end.id))
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_batch_limit", "500")

    def _make_lead(self, **vals):
        defaults = {
            "name": "Test Dead Lead",
            "type": "opportunity",
            "stage_id": self.stage_dead_end.id,
        }
        defaults.update(vals)
        return self.env["crm.lead"].create(defaults)

    def _backdate(self, lead, days):
        """Odoo defers writing stored computed fields (date_last_stage_update)
        to a later flush point — without flushing first, the ORM's own
        pending "now" value silently overwrites this raw SQL backdate the
        next time anything triggers a flush (e.g. the cron's own search()).
        Confirmed via a direct shell repro before adding this line."""
        lead.flush_recordset()
        dt = fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=days))
        self.env.cr.execute(
            "UPDATE crm_lead SET write_date=%s, date_last_stage_update=%s WHERE id=%s",
            (dt, dt, lead.id),
        )
        lead.invalidate_recordset()

    def _grace_activity(self, lead):
        return self.env["mail.activity"].search(
            [
                ("res_model", "=", "crm.lead"),
                ("res_id", "=", lead.id),
                ("summary", "=", "Stale Lead: set Lost Reason"),
            ],
            limit=1,
        )

    def _create_backdated_grace_activity(self, lead, days_old):
        """Simulate a grace activity that was created `days_old` days ago —
        create_date is an automatic field the ORM won't let us set directly,
        so backdate it with raw SQL the same way _backdate() does for
        date_last_stage_update."""
        todo = self.env.ref("mail.mail_activity_data_todo")
        activity = self.env["mail.activity"].create(
            {
                "res_model_id": self.env["ir.model"]._get_id("crm.lead"),
                "res_id": lead.id,
                "activity_type_id": todo.id,
                "summary": "Stale Lead: set Lost Reason",
                "user_id": self.env.user.id,
                "date_deadline": fields.Date.today(),
            }
        )
        activity.flush_recordset()
        dt = fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=days_old))
        self.env.cr.execute(
            "UPDATE mail_activity SET create_date=%s WHERE id=%s", (dt, activity.id)
        )
        activity.invalidate_recordset()
        return activity

    def test_cleanup_dry_run_selects_expected_fixture_set(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "dry_run")

        stale_lead = self._make_lead()
        self._backdate(stale_lead, 40)
        fresh_lead = self._make_lead()
        self._backdate(fresh_lead, 5)
        unrelated_stage_lead = self._make_lead(stage_id=self.stage_meeting.id)
        self._backdate(unrelated_stage_lead, 40)
        lost_reason = self.env["crm.lost.reason"].create({"name": "Test Lost Reason"})
        already_lost_lead = self._make_lead(lost_reason_id=lost_reason.id)
        self._backdate(already_lost_lead, 40)

        self.env["crm.lead"]._cron_dead_lead_cleanup()

        # Dry run must not write anything.
        stale_lead.invalidate_recordset()
        fresh_lead.invalidate_recordset()
        self.assertTrue(stale_lead.active)
        self.assertFalse(stale_lead.x_auto_archived_run)
        self.assertTrue(fresh_lead.active)

        # An attachment CSV should have been written somewhere reviewable,
        # and must select exactly the stale, dead-end, not-yet-lost lead —
        # not the fresh one, not the one in an unrelated stage, not the one
        # that already has a lost reason.
        attachment = self.env["ir.attachment"].search(
            [("name", "like", "sgc_dead_lead_cleanup_dryrun_%")], limit=1, order="id desc"
        )
        self.assertTrue(attachment, "Dry-run CSV attachment was not created")
        csv_rows = base64.b64decode(attachment.datas).decode("utf-8").splitlines()
        csv_ids = {row.split(",", 1)[0] for row in csv_rows[1:] if row}
        self.assertIn(str(stale_lead.id), csv_ids)
        self.assertNotIn(str(fresh_lead.id), csv_ids)
        self.assertNotIn(str(unrelated_stage_lead.id), csv_ids)
        self.assertNotIn(str(already_lost_lead.id), csv_ids)

    def test_cleanup_live_archives_and_is_idempotent(self):
        """A lead with an already-expired grace activity gets archived, and
        a second consecutive run is a no-op (archived leads drop out of the
        active=True domain)."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "live")

        stale_lead = self._make_lead()
        self._backdate(stale_lead, 40)
        self._create_backdated_grace_activity(stale_lead, days_old=8)
        stale_lead_id = stale_lead.id

        self.env["crm.lead"]._cron_dead_lead_cleanup()

        archived = self.env["crm.lead"].with_context(active_test=False).browse(stale_lead_id)
        self.assertFalse(archived.active)
        self.assertEqual(archived.probability, 0)
        self.assertTrue(archived.x_auto_archived_run)
        self.assertFalse(
            self.env["mail.activity"].search_count(
                [("res_model", "=", "crm.lead"), ("res_id", "=", stale_lead_id)]
            ),
            "Open activities should be cleared when a lead is auto-archived",
        )

        # Second consecutive run must select 0 additional records — the
        # archived lead is now active=False and drops out of the domain.
        run_marker_before = archived.x_auto_archived_run
        self.env["crm.lead"]._cron_dead_lead_cleanup()
        archived.invalidate_recordset()
        self.assertEqual(archived.x_auto_archived_run, run_marker_before)

    def test_cold_start_gives_grace_to_long_stale_lead(self):
        """A1 regression: the old rule archived anything 37+ days stale
        immediately on a first-ever run, with zero warning. A lead stale
        200 days but with no prior grace activity must get the grace
        activity — never be archived — on a cold start."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "live")

        stale_lead = self._make_lead()
        self._backdate(stale_lead, 200)
        stale_lead_id = stale_lead.id

        self.env["crm.lead"]._cron_dead_lead_cleanup()

        lead = self.env["crm.lead"].with_context(active_test=False).browse(stale_lead_id)
        self.assertTrue(lead.active, "A never-warned lead must not be archived, regardless of age")
        self.assertFalse(lead.x_auto_archived_run)
        self.assertTrue(
            self._grace_activity(lead),
            "A grace activity should have been created for this lead",
        )

    def test_expired_grace_archives(self):
        """A grace activity older than the grace period causes archival."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "live")

        stale_lead = self._make_lead()
        self._backdate(stale_lead, 45)
        self._create_backdated_grace_activity(stale_lead, days_old=10)
        stale_lead_id = stale_lead.id

        self.env["crm.lead"]._cron_dead_lead_cleanup()

        lead = self.env["crm.lead"].with_context(active_test=False).browse(stale_lead_id)
        self.assertFalse(lead.active)
        self.assertTrue(lead.x_auto_archived_run)

    def test_unexpired_grace_does_nothing(self):
        """A grace activity still within its window must not be archived,
        and must not get a second, duplicate grace activity either."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "live")

        stale_lead = self._make_lead()
        self._backdate(stale_lead, 33)
        self._create_backdated_grace_activity(stale_lead, days_old=2)
        stale_lead_id = stale_lead.id

        self.env["crm.lead"]._cron_dead_lead_cleanup()

        lead = self.env["crm.lead"].with_context(active_test=False).browse(stale_lead_id)
        self.assertTrue(lead.active, "A lead within its grace window must not be archived")
        self.assertFalse(lead.x_auto_archived_run)
        self.assertEqual(
            self.env["mail.activity"].search_count(
                [
                    ("res_model", "=", "crm.lead"),
                    ("res_id", "=", stale_lead_id),
                    ("summary", "=", "Stale Lead: set Lost Reason"),
                ]
            ),
            1,
            "Must not create a second grace activity while one is still active",
        )

    def test_reenable_after_gap_does_not_skip_grace(self):
        """Simulates the cron being disabled for a long stretch (e.g. during
        a restore-containment window) and re-enabled later: a lead that went
        stale during the gap and was never warned must still get grace on
        the first run after re-enabling, not be silently hard-archived
        because it "looks old enough" by dwell time alone."""
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("sgc_sales_playbook.dead_lead_cleanup_mode", "live")

        # Lead went stale well before the cron was re-enabled — dwell time
        # alone would have called this "well past the old 37-day cutoff".
        stale_lead = self._make_lead()
        self._backdate(stale_lead, 90)
        stale_lead_id = stale_lead.id

        # First run after the gap: no pre-existing grace activity exists,
        # so this must warn, not archive.
        self.env["crm.lead"]._cron_dead_lead_cleanup()
        lead = self.env["crm.lead"].with_context(active_test=False).browse(stale_lead_id)
        self.assertTrue(lead.active)
        self.assertTrue(self._grace_activity(lead))

        # Immediately re-running (grace activity is brand new, not expired)
        # must still not archive.
        self.env["crm.lead"]._cron_dead_lead_cleanup()
        lead.invalidate_recordset()
        self.assertTrue(lead.active)
