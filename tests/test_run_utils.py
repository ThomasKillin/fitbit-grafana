import unittest
from datetime import datetime

from fitbit_fetch.run_utils import build_date_list, write_and_reset_records


class RunUtilsTests(unittest.TestCase):
    def test_build_date_list_inclusive(self):
        start_date = datetime.strptime("2026-01-01", "%Y-%m-%d")
        end_date = datetime.strptime("2026-01-03", "%Y-%m-%d")
        self.assertEqual(build_date_list(start_date, end_date), ["2026-01-01", "2026-01-02", "2026-01-03"])

    def test_write_and_reset_records_returns_empty_list(self):
        observed = []

        def fake_writer(records):
            observed.extend(records)

        records = [{"measurement": "x", "fields": {"value": 1}}]
        result = write_and_reset_records(fake_writer, records)
        self.assertEqual(observed, records)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
