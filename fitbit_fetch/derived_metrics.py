"""Derived metric generation from collected direct records."""

from datetime import datetime, timedelta
import time


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _latest_measurement(points, measurement_name: str):
    candidates = [point for point in points if point.get("measurement") == measurement_name]
    if not candidates:
        return None
    return max(candidates, key=lambda point: point.get("time", ""))


def _derive_daily_load_from_hr_zones(points) -> float | None:
    latest_hr_zone = _latest_measurement(points, "HR zones")
    if latest_hr_zone is None:
        return None
    fields = latest_hr_zone.get("fields", {})
    normal = float(fields.get("Normal", 0) or 0)
    fat_burn = float(fields.get("Fat Burn", 0) or 0)
    cardio = float(fields.get("Cardio", 0) or 0)
    peak = float(fields.get("Peak", 0) or 0)
    return normal + (2 * fat_burn) + (3 * cardio) + (4 * peak)


def _derive_training_load_fields(points, end_date_str: str) -> dict | None:
    daily_load_by_date = {}
    for point in points:
        if point.get("measurement") != "HR zones":
            continue
        point_time = point.get("time", "")
        if "T" not in point_time:
            continue
        point_date = point_time.split("T", 1)[0]
        fields = point.get("fields", {})
        normal = float(fields.get("Normal", 0) or 0)
        fat_burn = float(fields.get("Fat Burn", 0) or 0)
        cardio = float(fields.get("Cardio", 0) or 0)
        peak = float(fields.get("Peak", 0) or 0)
        load_value = normal + (2 * fat_burn) + (3 * cardio) + (4 * peak)
        daily_load_by_date[point_date] = daily_load_by_date.get(point_date, 0.0) + load_value

    if not daily_load_by_date:
        return None

    end_date = datetime.fromisoformat(end_date_str).date()
    latest_available_date = max(daily_load_by_date.keys())
    daily_load = daily_load_by_date.get(end_date_str, daily_load_by_date.get(latest_available_date, 0.0))

    acute_days = [(end_date - timedelta(days=idx)).isoformat() for idx in range(0, 7)]
    chronic_days = [(end_date - timedelta(days=idx)).isoformat() for idx in range(0, 28)]

    acute_7d = sum(daily_load_by_date.get(day, 0.0) for day in acute_days) / 7.0
    chronic_28d = sum(daily_load_by_date.get(day, 0.0) for day in chronic_days) / 28.0
    load_ratio = acute_7d / chronic_28d if chronic_28d > 0 else 0.0

    return {
        "daily_load": round(float(daily_load), 2),
        "acute_7d": round(float(acute_7d), 2),
        "chronic_28d": round(float(chronic_28d), 2),
        "load_ratio": round(float(load_ratio), 4),
    }


def _derive_recovery_score(points) -> dict | None:
    latest_sleep = _latest_measurement(points, "Sleep Summary")
    latest_hrv = _latest_measurement(points, "HRV")
    latest_rhr = _latest_measurement(points, "RestingHR")

    if latest_sleep is None and latest_hrv is None and latest_rhr is None:
        return None

    sleep_minutes = float((latest_sleep or {}).get("fields", {}).get("minutesAsleep", 0) or 0)
    hrv_rmssd = float((latest_hrv or {}).get("fields", {}).get("dailyRmssd", 0) or 0)
    resting_hr = float((latest_rhr or {}).get("fields", {}).get("value", 0) or 0)
    daily_load = _derive_daily_load_from_hr_zones(points) or 0

    sleep_component = _clamp((sleep_minutes / 480.0) * 100.0, 0.0, 100.0)
    hrv_component = _clamp((hrv_rmssd / 60.0) * 100.0, 0.0, 100.0)
    # Lower resting HR contributes higher score.
    rhr_component = _clamp(((80.0 - resting_hr) / 30.0) * 100.0, 0.0, 100.0) if resting_hr > 0 else 50.0
    # Higher strain/load contributes lower score.
    strain_component = _clamp(100.0 - (daily_load / 2.0), 0.0, 100.0)

    score = (sleep_component + hrv_component + rhr_component + strain_component) / 4.0
    return {
        "score": round(score, 2),
        "sleep_component": round(sleep_component, 2),
        "hrv_component": round(hrv_component, 2),
        "rhr_component": round(rhr_component, 2),
        "strain_component": round(strain_component, 2),
    }


def _derive_cardio_fitness(points) -> dict | None:
    latest_rhr = _latest_measurement(points, "RestingHR")
    if latest_rhr is None:
        return None

    resting_hr = float((latest_rhr or {}).get("fields", {}).get("value", 0) or 0)
    if resting_hr <= 0:
        return None

    # Heuristic VO2 estimate from resting HR for trend-only use.
    vo2_estimate = _clamp(90.0 - (0.8 * resting_hr), 20.0, 70.0)
    return {
        "vo2_estimate": round(vo2_estimate, 2),
        "source": "heuristic_rhr",
        "confidence": 0.4,
    }


def _latest_value_by_date(points, measurement_name: str, field_name: str) -> dict:
    values = {}
    for point in points:
        if point.get("measurement") != measurement_name:
            continue
        point_time = point.get("time", "")
        if "T" not in point_time:
            continue
        date_str = point_time.split("T", 1)[0]
        fields = point.get("fields", {})
        raw_value = fields.get(field_name)
        if raw_value is None:
            continue
        try:
            values[date_str] = float(raw_value)
        except (TypeError, ValueError):
            continue
    return values


def _derive_delta_from_latest_two(by_date: dict) -> float | None:
    if len(by_date) < 2:
        return None
    sorted_dates = sorted(by_date.keys())
    latest_date = sorted_dates[-1]
    previous_date = sorted_dates[-2]
    return by_date[latest_date] - by_date[previous_date]


def _derive_correlation_signals(points) -> dict | None:

    signal_defs = [
        ("rhr_delta", "RestingHR", "value"),
        ("hrv_delta", "HRV", "dailyRmssd"),
        ("sleep_minutes_delta", "Sleep Summary", "minutesAsleep"),
        ("steps_delta", "Total Steps", "value"),
    ]

    out = {}
    for out_field, measurement, field in signal_defs:
        by_date = _latest_value_by_date(points, measurement, field)
        delta = _derive_delta_from_latest_two(by_date)
        if delta is None:
            continue
        out[out_field] = round(delta, 2)

    if not out:
        return None
    return out


def build_derived_points(
    *,
    points,
    devicename: str,
    end_date_str: str,
    enable_pipeline_health: bool,
    enable_recovery_score: bool,
    enable_training_load: bool,
    enable_cardio_fitness: bool,
    enable_correlation_signals: bool,
):
    derived_points = []
    metric_time = datetime.fromisoformat(end_date_str + "T00:00:00").isoformat() + "+00:00"

    if enable_training_load:
        training_load_fields = _derive_training_load_fields(points, end_date_str)
        if training_load_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived TrainingLoad",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": training_load_fields,
                }
            )

    if enable_recovery_score:
        recovery_fields = _derive_recovery_score(points)
        if recovery_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived RecoveryScore",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": recovery_fields,
                }
            )

    if enable_cardio_fitness:
        cardio_fitness_fields = _derive_cardio_fitness(points)
        if cardio_fitness_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived CardioFitness",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": cardio_fitness_fields,
                }
            )

    if enable_correlation_signals:
        correlation_fields = _derive_correlation_signals(points)
        if correlation_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived CorrelationSignals",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": correlation_fields,
                }
            )

    if enable_pipeline_health:
        derived_points.append(
            {
                "measurement": "Derived PipelineHealth",
                "time": datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00",
                "tags": {"Device": devicename, "MetricClass": "Derived"},
                "fields": {
                    "last_success_epoch": int(time.time()),
                    "minutes_since_success": 0.0,
                    "record_count_last_run": int(len(points)),
                },
            }
        )

    return derived_points
