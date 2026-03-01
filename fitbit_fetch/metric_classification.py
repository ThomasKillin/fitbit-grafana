"""Helpers for keeping direct/derived metric classes consistent."""


def annotate_points_with_metric_class(points, metric_class: str):
    annotated_points = []
    for point in points:
        annotated_point = dict(point)
        tags = dict(annotated_point.get("tags") or {})
        tags.setdefault("MetricClass", metric_class)
        annotated_point["tags"] = tags
        annotated_points.append(annotated_point)
    return annotated_points
