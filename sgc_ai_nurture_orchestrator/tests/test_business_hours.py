# -*- coding: utf-8 -*-
from datetime import datetime

import pytz

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "sgc_ai_nurture_orchestrator")
class TestBusinessHours(TransactionCase):
    """`_get_next_business_datetime` takes naive UTC in, naive UTC out.
    Every expected value below is worked out in Asia/Dubai (UTC+4, no DST)
    and converted back, so the test reads in the timezone the rule is
    actually about.
    """

    def _dubai(self, year, month, day, hour, minute=0):
        tz = pytz.timezone("Asia/Dubai")
        local = tz.localize(datetime(year, month, day, hour, minute))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def test_inside_window_unchanged(self):
        # Wednesday 2026-08-19 11:00 Dubai -- inside Sun-Thu 09:00-18:00.
        moment = self._dubai(2026, 8, 19, 11, 0)
        result = self.env["sgc.nurture.sequence"]._get_next_business_datetime(moment)
        self.assertEqual(result, moment)

    def test_before_opening_same_day(self):
        # Wednesday 06:00 Dubai -- rolls forward to 09:00 the same day.
        moment = self._dubai(2026, 8, 19, 6, 0)
        expected = self._dubai(2026, 8, 19, 9, 0)
        result = self.env["sgc.nurture.sequence"]._get_next_business_datetime(moment)
        self.assertEqual(result, expected)

    def test_after_closing_rolls_to_next_business_day(self):
        # Wednesday 20:00 Dubai -- rolls to Thursday 09:00.
        moment = self._dubai(2026, 8, 19, 20, 0)
        expected = self._dubai(2026, 8, 20, 9, 0)
        result = self.env["sgc.nurture.sequence"]._get_next_business_datetime(moment)
        self.assertEqual(result, expected)

    def test_friday_rolls_to_sunday(self):
        # Friday 2026-08-21 10:00 Dubai is off (Sun-Thu work week) -- rolls
        # to Sunday 2026-08-23 09:00, skipping Saturday too.
        moment = self._dubai(2026, 8, 21, 10, 0)
        expected = self._dubai(2026, 8, 23, 9, 0)
        result = self.env["sgc.nurture.sequence"]._get_next_business_datetime(moment)
        self.assertEqual(result, expected)

    def test_saturday_rolls_to_sunday(self):
        moment = self._dubai(2026, 8, 22, 10, 0)
        expected = self._dubai(2026, 8, 23, 9, 0)
        result = self.env["sgc.nurture.sequence"]._get_next_business_datetime(moment)
        self.assertEqual(result, expected)
