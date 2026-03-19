import unittest
from unittest.mock import Mock

import requests

from fitbit_fetch.endpoint_capability import EndpointSpec, check_endpoint_support, default_date_window


class EndpointCapabilityTests(unittest.TestCase):
    def test_default_date_window(self):
        start_date, end_date = default_date_window(14)
        self.assertRegex(start_date, r"\d{4}-\d{2}-\d{2}")
        self.assertRegex(end_date, r"\d{4}-\d{2}-\d{2}")

    def test_check_endpoint_support_supported(self):
        spec = EndpointSpec(name="ECG", url_template="https://example/{start}/{end}")

        def fake_request(_url):
            return {"items": []}

        result = check_endpoint_support(
            spec=spec,
            start_date="2026-03-01",
            end_date="2026-03-14",
            request_data_from_fitbit=fake_request,
        )
        self.assertTrue(result["supported"])
        self.assertEqual(result["status"], "supported")
        self.assertEqual(result["http_status"], 200)

    def test_check_endpoint_support_unavailable_on_404(self):
        spec = EndpointSpec(name="IRN", url_template="https://example/{start}/{end}")
        response = Mock(status_code=404)
        err = requests.exceptions.HTTPError(response=response)

        def fake_request(_url):
            raise err

        result = check_endpoint_support(
            spec=spec,
            start_date="2026-03-01",
            end_date="2026-03-14",
            request_data_from_fitbit=fake_request,
        )
        self.assertFalse(result["supported"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["http_status"], 404)

    def test_check_endpoint_support_error_on_500(self):
        spec = EndpointSpec(name="CardioFitness", url_template="https://example/{start}/{end}")
        response = Mock(status_code=500)
        err = requests.exceptions.HTTPError(response=response)

        def fake_request(_url):
            raise err

        result = check_endpoint_support(
            spec=spec,
            start_date="2026-03-01",
            end_date="2026-03-14",
            request_data_from_fitbit=fake_request,
        )
        self.assertFalse(result["supported"])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["http_status"], 500)


if __name__ == "__main__":
    unittest.main()

