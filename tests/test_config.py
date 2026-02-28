import os
import unittest
from unittest.mock import patch

from fitbit_fetch.config import load_config


class ConfigTests(unittest.TestCase):
    def test_auto_date_range_defaults_true_when_manual_start_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        self.assertTrue(config.auto_date_range)
        self.assertTrue(config.schedule_auto_update)

    def test_auto_date_range_false_values(self):
        with patch.dict(os.environ, {"AUTO_DATE_RANGE": "False"}, clear=True):
            config = load_config()
        self.assertFalse(config.auto_date_range)
        self.assertFalse(config.schedule_auto_update)

    def test_manual_start_disables_auto(self):
        with patch.dict(os.environ, {"MANUAL_START_DATE": "2026-01-01"}, clear=True):
            config = load_config()
        self.assertFalse(config.auto_date_range)
        self.assertFalse(config.schedule_auto_update)

    def test_influx_version_validation(self):
        with patch.dict(os.environ, {"INFLUXDB_VERSION": "3"}, clear=True):
            config = load_config()
        self.assertEqual(config.influxdb_version, "3")

    def test_rate_limit_buffer_override(self):
        with patch.dict(os.environ, {"FITBIT_RATE_LIMIT_BUFFER_SECONDS": "120"}, clear=True):
            config = load_config()
        self.assertEqual(config.fitbit_rate_limit_buffer_seconds, 120)

    def test_derived_feature_flags_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()
        self.assertTrue(config.enable_derived_pipeline_health)
        self.assertFalse(config.enable_derived_recovery_score)
        self.assertFalse(config.enable_derived_training_load)
        self.assertFalse(config.enable_derived_cardio_fitness)

    def test_derived_feature_flags_override(self):
        with patch.dict(
            os.environ,
            {
                "ENABLE_DERIVED_PIPELINE_HEALTH": "false",
                "ENABLE_DERIVED_RECOVERY_SCORE": "true",
                "ENABLE_DERIVED_TRAINING_LOAD": "1",
                "ENABLE_DERIVED_CARDIO_FITNESS": "true",
            },
            clear=True,
        ):
            config = load_config()
        self.assertFalse(config.enable_derived_pipeline_health)
        self.assertTrue(config.enable_derived_recovery_score)
        self.assertTrue(config.enable_derived_training_load)
        self.assertTrue(config.enable_derived_cardio_fitness)


if __name__ == "__main__":
    unittest.main()
