import unittest
from unittest.mock import Mock

import requests

from fitbit_fetch.collectors_direct import (
    collect_device_sync_health,
    collect_direct_cardio_fitness,
    collect_direct_ecg,
    collect_direct_irn,
)


class CollectorsDirectTests(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.warning_cache = set()
        self.records = []
        self.local_timezone = __import__("pytz").timezone("UTC")

    def test_collect_direct_cardio_fitness_parses_points(self):
        def fake_request(_url):
            return {"cardioScore": [{"dateTime": "2026-03-10", "value": {"vo2Max": 48.3}}]}

        collect_direct_cardio_fitness(
            request_data_from_fitbit=fake_request,
            start_date_str="2026-03-01",
            end_date_str="2026-03-10",
            local_timezone=self.local_timezone,
            devicename="PixelWatch4",
            collected_records=self.records,
            logger=self.logger,
            warning_cache=self.warning_cache,
        )
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["measurement"], "CardioFitness")
        self.assertEqual(self.records[0]["fields"]["vo2_max"], 48.3)

    def test_collect_direct_ecg_is_best_effort_on_404(self):
        response = Mock(status_code=404)
        err = requests.exceptions.HTTPError(response=response)

        def fake_request(_url):
            raise err

        collect_direct_ecg(
            request_data_from_fitbit=fake_request,
            start_date_str="2026-03-01",
            end_date_str="2026-03-10",
            local_timezone=self.local_timezone,
            devicename="PixelWatch4",
            collected_records=self.records,
            logger=self.logger,
            warning_cache=self.warning_cache,
        )
        self.assertEqual(len(self.records), 0)
        self.logger.warning.assert_called_once()

    def test_collect_direct_irn_parses_events(self):
        def fake_request(_url):
            return {"irnAlerts": [{"dateTime": "2026-03-11T12:00:00", "result": "possible_afib"}]}

        collect_direct_irn(
            request_data_from_fitbit=fake_request,
            start_date_str="2026-03-01",
            end_date_str="2026-03-11",
            local_timezone=self.local_timezone,
            devicename="PixelWatch4",
            collected_records=self.records,
            logger=self.logger,
            warning_cache=self.warning_cache,
        )
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["measurement"], "IRN")
        self.assertEqual(self.records[0]["tags"]["event_type"], "possible_afib")

    def test_collect_device_sync_health_records_minutes_since_sync(self):
        def fake_request(_url):
            return [
                {
                    "lastSyncTime": "2026-03-12T00:00:00",
                    "batteryLevel": 52,
                    "deviceVersion": "Pixel Watch 4",
                    "type": "TRACKER",
                }
            ]

        collect_device_sync_health(
            request_data_from_fitbit=fake_request,
            local_timezone=self.local_timezone,
            devicename="PixelWatch4",
            collected_records=self.records,
            logger=self.logger,
            warning_cache=self.warning_cache,
        )
        self.assertEqual(len(self.records), 1)
        self.assertEqual(self.records[0]["measurement"], "DeviceSyncHealth")
        self.assertIn("minutes_since_last_sync", self.records[0]["fields"])


if __name__ == "__main__":
    unittest.main()

