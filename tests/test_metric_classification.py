import unittest

from fitbit_fetch.metric_classification import annotate_points_with_metric_class


class MetricClassificationTests(unittest.TestCase):
    def test_adds_metric_class_when_missing(self):
        points = [{"measurement": "RestingHR", "tags": {"Device": "Watch1"}, "fields": {"value": 55}}]
        annotated = annotate_points_with_metric_class(points, "Direct")
        self.assertEqual(annotated[0]["tags"]["MetricClass"], "Direct")
        self.assertEqual(annotated[0]["tags"]["Device"], "Watch1")

    def test_preserves_existing_metric_class(self):
        points = [{"measurement": "Derived RecoveryScore", "tags": {"MetricClass": "Derived"}, "fields": {}}]
        annotated = annotate_points_with_metric_class(points, "Direct")
        self.assertEqual(annotated[0]["tags"]["MetricClass"], "Derived")

    def test_handles_missing_tags_and_does_not_mutate_input(self):
        points = [{"measurement": "Total Steps", "fields": {"value": 5000}}]
        annotated = annotate_points_with_metric_class(points, "Direct")
        self.assertEqual(annotated[0]["tags"]["MetricClass"], "Direct")
        self.assertNotIn("tags", points[0])


if __name__ == "__main__":
    unittest.main()
