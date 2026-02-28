import unittest

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
        )
        measurements = {point["measurement"] for point in derived}
        self.assertIn("Derived TrainingLoad", measurements)
        self.assertIn("Derived RecoveryScore", measurements)
        self.assertTrue(all(point["tags"]["MetricClass"] == "Derived" for point in derived))

    def test_cardio_fitness_point_when_resting_hr_present(self):
        points = [{"measurement": "RestingHR", "time": "2026-02-28T00:00:00+00:00", "fields": {"value": 55}}]
        derived = build_derived_points(
            points=points,
            devicename="ChargeX",
            end_date_str="2026-02-28",
            enable_pipeline_health=False,
            enable_recovery_score=False,
            enable_training_load=False,
            enable_cardio_fitness=True,
        )
        self.assertEqual(len(derived), 1)
        self.assertEqual(derived[0]["measurement"], "Derived CardioFitness")
        self.assertEqual(derived[0]["fields"]["source"], "heuristic_rhr")
        self.assertEqual(derived[0]["fields"]["confidence"], 0.4)
        self.assertGreater(derived[0]["fields"]["vo2_estimate"], 0)


if __name__ == "__main__":
    unittest.main()
