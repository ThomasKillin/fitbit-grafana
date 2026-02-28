import unittest
from datetime import datetime

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
            get_new_access_token=lambda *_: None,
            client_id="cid",
            client_secret="csecret",
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


if __name__ == "__main__":
    unittest.main()
