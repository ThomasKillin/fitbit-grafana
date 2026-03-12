import unittest

from fitbit_fetch.derived_backfill import compute_backfill_dates, run_derived_startup_auto_backfill


class _FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, *args, **kwargs):
        self.messages.append(("info", args, kwargs))

    def debug(self, *args, **kwargs):
        self.messages.append(("debug", args, kwargs))


class _FakeInfluxWriter:
    def __init__(self, points_by_day):
        self.points_by_day = points_by_day
        self.write_calls = []
        self.fetch_calls = []

    def fetch_direct_points_for_day(self, day_str, _measurements):
        self.fetch_calls.append(day_str)
        return self.points_by_day.get(day_str, [])

    def write_points(self, points):
        self.write_calls.append(points)


class DerivedBackfillTests(unittest.TestCase):
    def test_compute_backfill_dates_applies_safety_cap(self):
        dates = compute_backfill_dates(
            end_date_str="2026-03-10",
            requested_days=30,
            max_days_per_run=5,
        )
        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[0], "2026-03-06")
        self.assertEqual(dates[-1], "2026-03-10")

    def test_run_backfill_skips_when_disabled(self):
        logger = _FakeLogger()
        writer = _FakeInfluxWriter(points_by_day={})
        run_derived_startup_auto_backfill(
            enabled=False,
            influx_writer=writer,
            logger=logger,
            devicename="ChargeX",
            end_date_str="2026-03-10",
            requested_days=5,
            max_days_per_run=5,
            enable_recovery_score=True,
            enable_training_load=False,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            sleep_fn=lambda *_: None,
        )
        self.assertEqual(writer.fetch_calls, [])
        self.assertEqual(writer.write_calls, [])

    def test_run_backfill_processes_days_and_writes_derived_points(self):
        logger = _FakeLogger()
        writer = _FakeInfluxWriter(
            points_by_day={
                "2026-03-09": [
                    {"measurement": "Sleep Summary", "time": "2026-03-09T00:00:00+00:00", "fields": {"minutesAsleep": 410}},
                    {"measurement": "HRV", "time": "2026-03-09T00:00:00+00:00", "fields": {"dailyRmssd": 42}},
                    {"measurement": "RestingHR", "time": "2026-03-09T00:00:00+00:00", "fields": {"value": 58}},
                    {"measurement": "HR zones", "time": "2026-03-09T00:00:00+00:00", "fields": {"Normal": 10, "Fat Burn": 4, "Cardio": 2, "Peak": 1}},
                ],
                "2026-03-10": [],
            }
        )
        sleeps = []
        run_derived_startup_auto_backfill(
            enabled=True,
            influx_writer=writer,
            logger=logger,
            devicename="ChargeX",
            end_date_str="2026-03-10",
            requested_days=2,
            max_days_per_run=10,
            enable_recovery_score=True,
            enable_training_load=True,
            enable_cardio_fitness=True,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            sleep_fn=lambda seconds: sleeps.append(seconds),
        )
        self.assertEqual(writer.fetch_calls, ["2026-03-09", "2026-03-10"])
        self.assertEqual(len(writer.write_calls), 1)
        measurements = {point["measurement"] for point in writer.write_calls[0]}
        self.assertIn("Derived RecoveryScore", measurements)
        self.assertIn("Derived TrainingLoad", measurements)
        self.assertIn("Derived CardioFitness", measurements)
        self.assertEqual(sleeps, [0.2])


if __name__ == "__main__":
    unittest.main()
