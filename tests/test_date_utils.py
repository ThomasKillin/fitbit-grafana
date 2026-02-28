import unittest
from datetime import timezone

from fitbit_fetch.date_utils import build_date_range, refresh_auto_date_range, yield_dates_with_gap


class DateUtilsTests(unittest.TestCase):
    def test_build_date_range_auto(self):
        start_date, end_date, start_date_str, end_date_str = build_date_range(
            local_timezone=timezone.utc,
            auto_date_range=True,
            auto_update_date_range=1,
            manual_start_date=None,
            manual_end_date="2026-01-10",
        )
        self.assertLessEqual(start_date, end_date)
        self.assertLessEqual(start_date_str, end_date_str)

    def test_build_date_range_manual(self):
        start_date, end_date, start_date_str, end_date_str = build_date_range(
            local_timezone=timezone.utc,
            auto_date_range=False,
            auto_update_date_range=1,
            manual_start_date="2026-01-01",
            manual_end_date="2026-01-03",
        )
        self.assertEqual(start_date_str, "2026-01-01")
        self.assertEqual(end_date_str, "2026-01-03")
        self.assertEqual((end_date - start_date).days, 2)

    def test_refresh_auto_date_range(self):
        start_date, end_date, start_date_str, end_date_str = refresh_auto_date_range(
            local_timezone=timezone.utc,
            auto_update_date_range=2,
        )
        self.assertLessEqual(start_date, end_date)
        self.assertLessEqual(start_date_str, end_date_str)

    def test_yield_dates_with_gap(self):
        date_list = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
        chunks = list(yield_dates_with_gap(date_list, 2))
        self.assertEqual(chunks, [("2026-01-01", "2026-01-03"), ("2026-01-03", "2026-01-04")])


if __name__ == "__main__":
    unittest.main()
