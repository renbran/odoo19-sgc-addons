from datetime import date, timedelta

from odoo.tests import TransactionCase, tagged

from ..lib import lifecycle

T = date(2026, 11, 1)


def state(**kw):
    values = dict(today=T, activated=True, days_overdue=0, end_date=None, archive_since=None, archive_days=90)
    values.update(kw)
    return lifecycle.target_state(**values)


@tagged("post_install", "-at_install", "layer3")
class TestLifecycle(TransactionCase):
    def test_not_activated(self):
        self.assertEqual(state(activated=False), (None, None))

    def test_overdue_schedule_follows_msa_table(self):
        expected = {0: "active", 1: "grace", 7: "grace", 8: "read_only", 14: "read_only", 29: "read_only", 30: "archive"}
        for days, want in expected.items():
            with self.subTest(days=days):
                self.assertEqual(state(days_overdue=days)[0], want)

    def test_archive_then_deletion(self):
        self.assertEqual(state(days_overdue=45, archive_since=T - timedelta(days=89)), ("archive", "overdue"))
        self.assertEqual(state(days_overdue=200, archive_since=T - timedelta(days=90)), ("deleted", "retention_expired"))

    def test_cancellation_gives_30_days_read_only(self):
        end = T - timedelta(days=10)
        self.assertEqual(state(end_date=end), ("read_only", "cancelled"))
        self.assertEqual(state(end_date=T - timedelta(days=30)), ("archive", "cancelled"))
        self.assertEqual(state(end_date=T - timedelta(days=120)), ("deleted", "retention_expired"))
        self.assertEqual(state(end_date=T + timedelta(days=5)), ("active", "paid"))

    def test_notice_needs_60_days(self):
        step = lambda d: d + timedelta(days=91)  # noqa: E731 - quarterly-ish cycles
        self.assertEqual(lifecycle.notice_end_date(T, T + timedelta(days=60), step), T + timedelta(days=60))
        self.assertEqual(lifecycle.notice_end_date(T, T + timedelta(days=59), step), T + timedelta(days=150))
