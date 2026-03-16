import unittest
from unittest.mock import patch, MagicMock

from fitbit_fetch.ask_ai import answer_question, infer_target, infer_window_days, summarize_series


class _FakeInfluxWriter:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query_metric_series(self, *, measurement, field, days, metric_class):
        self.calls.append(
            {
                "measurement": measurement,
                "field": field,
                "days": days,
                "metric_class": metric_class,
            }
        )
        return self.rows


class AskAiTests(unittest.TestCase):
    def test_infer_target(self):
        target = infer_target("How is my recovery score over the last 2 weeks?")
        self.assertIsNotNone(target)
        self.assertEqual(target.measurement, "Derived RecoveryScore")

    def test_infer_window_days(self):
        self.assertEqual(infer_window_days("last 3 weeks"), 21)
        self.assertEqual(infer_window_days("last 10 days"), 10)
        self.assertEqual(infer_window_days("last 2 months"), 60)
        self.assertEqual(infer_window_days("today"), 1)

    def test_summarize_series(self):
        summary = summarize_series(
            values=[{"time": "t1", "value": 50.0}, {"time": "t2", "value": 55.0}],
            label="Recovery score",
            unit="score",
            days=14,
        )
        self.assertEqual(summary["points"], 2)
        self.assertEqual(summary["latest"], 55.0)
        self.assertEqual(summary["delta"], 5.0)

    def test_answer_question_local_path(self):
        writer = _FakeInfluxWriter(
            rows=[
                {"time": "2026-03-01T00:00:00+00:00", "value": 57.0},
                {"time": "2026-03-02T00:00:00+00:00", "value": 55.0},
            ]
        )
        out = answer_question(
            question="How has my resting heart rate changed in last 7 days?",
            influx_writer=writer,
            openai_api_key=None,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["days"], 7)
        self.assertEqual(out["metric"], "Resting heart rate")
        self.assertEqual(writer.calls[0]["measurement"], "RestingHR")
        self.assertIn("latest", out["summary"])

    def test_answer_question_unknown_metric(self):
        writer = _FakeInfluxWriter(rows=[])
        out = answer_question(
            question="How is my hydration trend?",
            influx_writer=writer,
            openai_api_key=None,
        )
        self.assertFalse(out["ok"])
        self.assertIn("Could not infer a metric", out["error"])

    @patch("fitbit_fetch.ask_ai.requests.post")
    def test_answer_question_ollama_provider(self, post_mock):
        writer = _FakeInfluxWriter(
            rows=[
                {"time": "2026-03-01T00:00:00+00:00", "value": 57.0},
                {"time": "2026-03-02T00:00:00+00:00", "value": 55.0},
            ]
        )
        fake_response = MagicMock()
        fake_response.json.return_value = {"response": "Local model summary"}
        fake_response.raise_for_status.return_value = None
        post_mock.return_value = fake_response

        out = answer_question(
            question="How has my resting heart rate changed in last 7 days?",
            influx_writer=writer,
            ai_provider="ollama",
            openai_api_key=None,
            ollama_model="llama3.1:8b",
            ollama_base_url="http://localhost:11434",
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["answer"], "Local model summary")
        self.assertEqual(out["ai_provider"], "ollama")
        post_mock.assert_called_once()
        called_url = post_mock.call_args.args[0]
        self.assertEqual(called_url, "http://localhost:11434/api/generate")


if __name__ == "__main__":
    unittest.main()
