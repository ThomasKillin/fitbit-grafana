import unittest
from datetime import date, timedelta
from datetime import datetime

from fitbit_fetch.derived_metrics import build_derived_points


class DerivedMetricsTests(unittest.TestCase):
    def test_pipeline_health_point_added_by_default_flag(self):
        points = [{"measurement": "Total Steps", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 1000}}]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=True,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["measurement"], "Derived PipelineHealth")
        self.assertEqual(derived[0]["fields"]["record_count_last_run"], 1)
        self.assertEqual(derived[0]["tags"]["MetricClass"], "Derived")

    def test_recovery_and_training_load_points_when_inputs_present(self):
        points = [
            {"measurement": "HR zones", "time": "2026-02-28T00:00:00+00:00", "fields": {"Normal": 10, "Fat Burn": 5, "Cardio": 2, "Peak": 1}},
            {"measurement": "Sleep Summary", "time": "2026-02-28T00:00:00+00:00", "fields": {"minutesAsleep": 420}},
            {"measurement": "HRV", "time": "2026-02-28T00:00:00+00:00", "fields": {"dailyRmssd": 45}},
            {"measurement": "RestingHR", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 58}},
        ]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=False,
            enable_recovery_score=True,
            enable_training_load=True,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        measurements = {point["measurement"] for point in derived}
        self.assertIn("Derived TrainingLoad", measurements)
        self.assertIn("Derived RecoveryScore", measurements)
        self.assertTrue(all(point["tags"]["MetricClass"] == "Derived" for point in derived))

    def test_cardio_fitness_point_when_resting_hr_present(self):
        points = [
            {"measurement": "RestingHR", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 55}},
            {"measurement": "CardioFitness", "time": "2026-02-28T00:00:00+00:00", "fields": {"vo2_max": 50.0}},
        ]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=False,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=True,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        measurements = {point["measurement"] for point in derived}
        self.assertIn("Derived CardioFitness", measurements)
        self.assertIn("Derived CardioFitnessDelta", measurements)
        cardio = next(point for point in derived if point["measurement"] == "Derived CardioFitness")
        self.assertEqual(cardio["fields"]["source"], "heuristic_rhr")
        self.assertEqual(cardio["fields"]["confidence"], 0.4)
        self.assertGreater(cardio["fields"]["vo2_estimate"], 0)

    def test_training_load_rolling_windows(self):
        end_date = date(2026, 2, 28)
        points = []
        for idx in range(0, 28):
            day = (end_date - timedelta(days=idx)).isoformat()
            points.append(
                {
                    "measurement": "HR zones",
                    "time": f"{day}T00:00:00+00:00",
                    "fields": {"Normal": 10, "Fat Burn": 0, "Cardio": 0, "Peak": 0},
                }
            )

        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str=end_date.isoformat(),
            enable_pipeline_health=False,
            enable_recovery_score=False,
            enable_training_load=True,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["measurement"], "Derived TrainingLoad")
        self.assertEqual(derived[0]["fields"]["daily_load"], 10.0)
        self.assertEqual(derived[0]["fields"]["acute_7d"], 10.0)
        self.assertEqual(derived[0]["fields"]["chronic_28d"], 10.0)
        self.assertEqual(derived[0]["fields"]["load_ratio"], 1.0)

    def test_correlation_signals_day_over_day_deltas(self):
        points = [
            {"measurement": "RestingHR", "time": "2026-02-27T00:00:00+00:00", "fields": {"value": 58}},
            {"measurement": "RestingHR", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 56}},
            {"measurement": "HRV", "time": "2026-02-27T00:00:00+00:00", "fields": {"dailyRmssd": 40}},
            {"measurement": "HRV", "time": "2026-02-28T00:00:00+00:00", "fields": {"dailyRmssd": 44}},
            {"measurement": "Sleep Summary", "time": "2026-02-27T00:00:00+00:00", "fields": {"minutesAsleep": 410}},
            {"measurement": "Sleep Summary", "time": "2026-02-28T00:00:00+00:00", "fields": {"minutesAsleep": 430}},
            {"measurement": "Total Steps", "time": "2026-02-27T00:00:00+00:00", "fields": {"value": 9000}},
            {"measurement": "Total Steps", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 10250}},
        ]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=False,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=False,
            enable_correlation_signals=True,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["measurement"], "Derived CorrelationSignals")
        self.assertEqual(derived[0]["fields"]["rhr_delta"], -2.0)
        self.assertEqual(derived[0]["fields"]["hrv_delta"], 4.0)
        self.assertEqual(derived[0]["fields"]["sleep_minutes_delta"], 20.0)
        self.assertEqual(derived[0]["fields"]["steps_delta"], 1250.0)

    def test_correlation_signals_uses_latest_two_available_days(self):
        points = [
            {"measurement": "RestingHR", "time": "2026-02-24T23:00:00+00:00", "fields": {"value": 60}},
            {"measurement": "RestingHR", "time": "2026-02-25T23:00:00+00:00", "fields": {"value": 57}},
        ]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=False,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=False,
            enable_correlation_signals=True,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=None,
        )
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["measurement"], "Derived CorrelationSignals")
        self.assertEqual(derived[0]["fields"]["rhr_delta"], -3.0)

    def test_pipeline_health_minutes_since_previous_success(self):
        derived = build_derived_points(
            points=[{"measurement": "Total Steps", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 100}}],
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=True,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=False,
            enable_zscores=False,
            enable_trend_signals=False,
            enable_readiness_flags=False,
            pipeline_previous_success_epoch=0,
        )
        self.assertEqual(derived[0]["measurement"], "Derived PipelineHealth")
        self.assertGreaterEqual(derived[0]["fields"]["minutes_since_success"], 1.0)
        self.assertIsNotNone(datetime.fromisoformat(derived[0]["time"]).tzinfo)

    def test_correlation_matrix_zscores_trends_and_flags(self):
        end_date = date(2026, 2, 28)
        points = []
        for idx in range(0, 28):
            day = (end_date - timedelta(days=idx)).isoformat()
            points.extend(
                [
                    {"measurement": "RestingHR", "time": f"{day}T00:00:00+00:00", "fields": {"value": 60 - (idx % 5)}},
                    {"measurement": "HRV", "time": f"{day}T00:00:00+00:00", "fields": {"dailyRmssd": 35 + (idx % 7)}},
                    {"measurement": "Sleep Summary", "time": f"{day}T00:00:00+00:00", "fields": {"minutesAsleep": 390 + (idx % 20)}},
                    {"measurement": "Total Steps", "time": f"{day}T00:00:00+00:00", "fields": {"value": 8000 + (idx * 50)}},
                    {"measurement": "HR zones", "time": f"{day}T00:00:00+00:00", "fields": {"Normal": 10 + (idx % 3), "Fat Burn": 4, "Cardio": 2, "Peak": 1}},
                ]
            )

        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str=end_date.isoformat(),
            enable_pipeline_health=False,
            enable_recovery_score=True,
            enable_training_load=True,
            enable_cardio_fitness=False,
            enable_correlation_signals=False,
            enable_correlation_matrix=True,
            enable_zscores=True,
            enable_trend_signals=True,
            enable_readiness_flags=True,
            pipeline_previous_success_epoch=None,
        )
        measurements = {point["measurement"] for point in derived}
        self.assertIn("Derived CorrelationMatrix", measurements)
        self.assertIn("Derived ZScores", measurements)
        self.assertIn("Derived TrendSignals", measurements)
        self.assertIn("Derived ReadinessFlags", measurements)

        recovery = next(p for p in derived if p["measurement"] == "Derived RecoveryScore")
        self.assertIn("confidence", recovery["fields"])
        self.assertIn("missing_inputs_count", recovery["fields"])


if __name__ == "__main__":
    unittest.main()
