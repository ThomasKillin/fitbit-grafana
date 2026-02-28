import unittest
from datetime import datetime
from unittest.mock import patch

from fitbit_fetch.runner import run_startup_or_bulk_update


class RunnerTests(unittest.TestCase):
    def test_run_startup_auto_mode_executes_expected_calls(self):
        calls = []
        state = {"records": [{"measurement": "x"}]}

        def mark(name):
            calls.append(name)

        def fake_build_date_list(start_date, end_date):
            self.assertIsInstance(start_date, datetime)
            self.assertIsInstance(end_date, datetime)
            return ["2026-01-01"]

        def fake_write_points_to_influxdb(records):
            calls.append(f"write:{len(records)}")

        def fake_write_and_reset_records(writer, records):
            writer(records)
            return []

        run_startup_or_bulk_update(
            auto_date_range=True,
            start_date=datetime.strptime("2026-01-01", "%Y-%m-%d"),
            end_date=datetime.strptime("2026-01-01", "%Y-%m-%d"),
            start_date_str="2026-01-01",
            end_date_str="2026-01-01",
            schedule_module=None,
            logger=type("L", (), {"warn": lambda *_: None, "info": lambda *_: None})(),
            get_new_access_token=lambda: None,
            build_date_list=fake_build_date_list,
            get_intraday_data_limit_1d=lambda *_: mark("intraday"),
            get_daily_data_limit_30d=lambda *_: mark("30d"),
            get_daily_data_limit_100d=lambda *_: mark("100d"),
            get_daily_data_limit_365d=lambda *_: mark("365d"),
            get_daily_data_limit_none=lambda *_: mark("none"),
            get_battery_level=lambda: mark("battery"),
            fetch_latest_activities=lambda *_: mark("activities"),
            write_points_to_influxdb=fake_write_points_to_influxdb,
            write_and_reset_records=fake_write_and_reset_records,
            yield_dates_with_gap=lambda *_: [],
            get_collected_records=lambda: state["records"],
            set_collected_records=lambda records: state.update(records=records),
        )

        self.assertEqual(
            calls,
            ["intraday", "30d", "100d", "365d", "none", "battery", "activities", "write:1"],
        )
        self.assertEqual(state["records"], [])

    def test_run_startup_bulk_mode_executes_expected_batches(self):
        state = {"records": [{"measurement": "x"}]}
        counts = {
            "intraday": 0,
            "30d": 0,
            "100d": 0,
            "365d": 0,
            "none": 0,
            "fetch": 0,
            "write": 0,
            "run_pending": 0,
            "schedule_every": 0,
        }

        class FakeEvery:
            @property
            def hours(self):
                return self

            def do(self, _func):
                return None

        class FakeSchedule:
            def every(self, _n):
                counts["schedule_every"] += 1
                return FakeEvery()

            def run_pending(self):
                counts["run_pending"] += 1

        def fake_write_points_to_influxdb(_records):
            counts["write"] += 1

        def fake_write_and_reset_records(writer, records):
            writer(records)
            return []

        def fake_yield_dates_with_gap(_date_list, gap):
            if gap == 360:
                return [("2026-01-01", "2026-01-02")]
            if gap == 98:
                return [("2026-01-01", "2026-01-02")]
            if gap == 28:
                return [("2026-01-01", "2026-01-02")]
            return []

        with patch("builtins.print"):
            run_startup_or_bulk_update(
                auto_date_range=False,
                start_date=datetime.strptime("2026-01-01", "%Y-%m-%d"),
                end_date=datetime.strptime("2026-01-02", "%Y-%m-%d"),
                start_date_str="2026-01-01",
                end_date_str="2026-01-02",
                schedule_module=FakeSchedule(),
                logger=type("L", (), {"warn": lambda *_: None, "info": lambda *_: None})(),
                get_new_access_token=lambda: None,
                build_date_list=lambda *_: ["2026-01-01", "2026-01-02"],
                get_intraday_data_limit_1d=lambda *_: counts.__setitem__("intraday", counts["intraday"] + 1),
                get_daily_data_limit_30d=lambda *_: counts.__setitem__("30d", counts["30d"] + 1),
                get_daily_data_limit_100d=lambda *_: counts.__setitem__("100d", counts["100d"] + 1),
                get_daily_data_limit_365d=lambda *_: counts.__setitem__("365d", counts["365d"] + 1),
                get_daily_data_limit_none=lambda *_: counts.__setitem__("none", counts["none"] + 1),
                get_battery_level=lambda: None,
                fetch_latest_activities=lambda *_: counts.__setitem__("fetch", counts["fetch"] + 1),
                write_points_to_influxdb=fake_write_points_to_influxdb,
                write_and_reset_records=fake_write_and_reset_records,
                yield_dates_with_gap=fake_yield_dates_with_gap,
                get_collected_records=lambda: state["records"],
                set_collected_records=lambda records: state.update(records=records),
            )

        self.assertEqual(counts["schedule_every"], 1)
        self.assertEqual(counts["fetch"], 1)
        self.assertEqual(counts["none"], 1)
        self.assertEqual(counts["365d"], 1)
        self.assertEqual(counts["100d"], 1)
        self.assertEqual(counts["30d"], 1)
        self.assertEqual(counts["intraday"], 2)
        self.assertEqual(counts["run_pending"], 6)
        self.assertEqual(counts["write"], 7)


if __name__ == "__main__":
    unittest.main()
