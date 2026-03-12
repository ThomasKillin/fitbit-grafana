"""Derived metric generation from collected direct records."""

from datetime import datetime, timedelta, timezone
import time
import math


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


def _derive_daily_load_by_date(points) -> dict:
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
    return daily_load_by_date


def _derive_training_load_fields(points, end_date_str: str) -> dict | None:
    daily_load_by_date = _derive_daily_load_by_date(points)

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

    sleep_present = latest_sleep is not None
    hrv_present = latest_hrv is not None
    rhr_present = latest_rhr is not None
    load_present = _derive_daily_load_from_hr_zones(points) is not None

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
        "confidence": round((sum([sleep_present, hrv_present, rhr_present, load_present]) / 4.0), 3),
        "missing_inputs_count": int(4 - sum([sleep_present, hrv_present, rhr_present, load_present])),
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


def _date_window(end_date_str: str, days: int) -> list[str]:
    end_date = datetime.fromisoformat(end_date_str).date()
    return [(end_date - timedelta(days=idx)).isoformat() for idx in range(days - 1, -1, -1)]


def _pearson_corr(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3 or len(ys) < 3:
        return None
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    cov = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    var_x = sum((x - x_mean) ** 2 for x in xs)
    var_y = sum((y - y_mean) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return float(cov / math.sqrt(var_x * var_y))


def _corr_with_lag(series_x: dict, series_y: dict, end_date_str: str, window_days: int, lag_days: int = 0) -> float | None:
    end_date = datetime.fromisoformat(end_date_str).date()
    xs = []
    ys = []
    for idx in range(window_days):
        y_date = (end_date - timedelta(days=idx))
        x_date = y_date - timedelta(days=lag_days)
        x_val = series_x.get(x_date.isoformat())
        y_val = series_y.get(y_date.isoformat())
        if x_val is None or y_val is None:
            continue
        xs.append(x_val)
        ys.append(y_val)
    corr = _pearson_corr(xs, ys)
    if corr is None:
        return None
    return round(corr, 4)


def _latest_zscore(series: dict, end_date_str: str, window_days: int = 28) -> float | None:
    dates = _date_window(end_date_str, window_days)
    values = [series[d] for d in dates if d in series]
    if len(values) < 5:
        return None
    latest_date = max([d for d in dates if d in series])
    latest = float(series[latest_date])
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        return 0.0
    z = (latest - mean) / std
    return round(float(z), 4)


def _latest_slope(series: dict, end_date_str: str, window_days: int = 7) -> float | None:
    dates = _date_window(end_date_str, window_days)
    values = [series[d] for d in dates if d in series]
    if len(values) < 3:
        return None
    x = list(range(len(values)))
    x_mean = sum(x) / len(x)
    y_mean = sum(values) / len(values)
    num = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    den = sum((xi - x_mean) ** 2 for xi in x)
    if den == 0:
        return None
    slope = num / den
    return round(slope, 4)


def _recovery_series_by_date(points) -> dict:
    sleep_series = _latest_value_by_date(points, "Sleep Summary", "minutesAsleep")
    hrv_series = _latest_value_by_date(points, "HRV", "dailyRmssd")
    rhr_series = _latest_value_by_date(points, "RestingHR", "value")
    load_series = _derive_daily_load_by_date(points)
    dates = sorted(set(sleep_series.keys()) | set(hrv_series.keys()) | set(rhr_series.keys()) | set(load_series.keys()))
    out = {}
    for d in dates:
        sleep_minutes = float(sleep_series.get(d, 0.0) or 0.0)
        hrv_rmssd = float(hrv_series.get(d, 0.0) or 0.0)
        resting_hr = float(rhr_series.get(d, 0.0) or 0.0)
        daily_load = float(load_series.get(d, 0.0) or 0.0)
        if sleep_minutes == 0 and hrv_rmssd == 0 and resting_hr == 0 and daily_load == 0:
            continue
        sleep_component = _clamp((sleep_minutes / 480.0) * 100.0, 0.0, 100.0)
        hrv_component = _clamp((hrv_rmssd / 60.0) * 100.0, 0.0, 100.0)
        rhr_component = _clamp(((80.0 - resting_hr) / 30.0) * 100.0, 0.0, 100.0) if resting_hr > 0 else 50.0
        strain_component = _clamp(100.0 - (daily_load / 2.0), 0.0, 100.0)
        out[d] = round((sleep_component + hrv_component + rhr_component + strain_component) / 4.0, 4)
    return out


def _derive_correlation_matrix(points, end_date_str: str) -> dict | None:
    load_series = _derive_daily_load_by_date(points)
    recovery_series = _recovery_series_by_date(points)
    rhr_series = _latest_value_by_date(points, "RestingHR", "value")
    hrv_series = _latest_value_by_date(points, "HRV", "dailyRmssd")
    sleep_series = _latest_value_by_date(points, "Sleep Summary", "minutesAsleep")
    steps_series = _latest_value_by_date(points, "Total Steps", "value")

    fields = {}
    corr_defs = [
        ("corr_rhr_vs_hrv_14d", rhr_series, hrv_series, 14, 0),
        ("corr_sleep_vs_recovery_14d", sleep_series, recovery_series, 14, 0),
        ("corr_steps_vs_recovery_14d", steps_series, recovery_series, 14, 0),
        ("corr_load_vs_recovery_14d", load_series, recovery_series, 14, 0),
        ("corr_load_vs_recovery_lag1_14d", load_series, recovery_series, 14, 1),
        ("corr_load_vs_recovery_lag2_14d", load_series, recovery_series, 14, 2),
    ]
    for name, sx, sy, window, lag in corr_defs:
        corr = _corr_with_lag(sx, sy, end_date_str, window, lag)
        if corr is not None:
            fields[name] = corr
    return fields or None


def _derive_zscores(points, end_date_str: str) -> dict | None:
    load_series = _derive_daily_load_by_date(points)
    recovery_series = _recovery_series_by_date(points)
    series_defs = [
        ("z_rhr", _latest_value_by_date(points, "RestingHR", "value")),
        ("z_hrv", _latest_value_by_date(points, "HRV", "dailyRmssd")),
        ("z_sleep_minutes", _latest_value_by_date(points, "Sleep Summary", "minutesAsleep")),
        ("z_steps", _latest_value_by_date(points, "Total Steps", "value")),
        ("z_training_load", load_series),
        ("z_recovery_score", recovery_series),
    ]
    fields = {}
    for name, series in series_defs:
        z = _latest_zscore(series, end_date_str, 28)
        if z is not None:
            fields[name] = z
    return fields or None


def _derive_trend_signals(points, end_date_str: str) -> dict | None:
    load_series = _derive_daily_load_by_date(points)
    recovery_series = _recovery_series_by_date(points)
    series_defs = [
        ("slope_7d_rhr", _latest_value_by_date(points, "RestingHR", "value")),
        ("slope_7d_hrv", _latest_value_by_date(points, "HRV", "dailyRmssd")),
        ("slope_7d_sleep_minutes", _latest_value_by_date(points, "Sleep Summary", "minutesAsleep")),
        ("slope_7d_steps", _latest_value_by_date(points, "Total Steps", "value")),
        ("slope_7d_training_load", load_series),
        ("slope_7d_recovery_score", recovery_series),
    ]
    fields = {}
    for name, series in series_defs:
        slope = _latest_slope(series, end_date_str, 7)
        if slope is not None:
            fields[name] = slope
    return fields or None


def _derive_readiness_flags(points, end_date_str: str) -> dict | None:
    recovery_fields = _derive_recovery_score(points)
    training_fields = _derive_training_load_fields(points, end_date_str)
    if recovery_fields is None and training_fields is None:
        return None

    recovery_score = float((recovery_fields or {}).get("score", 50.0))
    confidence = float((recovery_fields or {}).get("confidence", 0.0))
    missing_inputs_count = int((recovery_fields or {}).get("missing_inputs_count", 4))
    rhr_component = float((recovery_fields or {}).get("rhr_component", 50.0))
    hrv_component = float((recovery_fields or {}).get("hrv_component", 0.0))
    sleep_component = float((recovery_fields or {}).get("sleep_component", 0.0))
    load_ratio = float((training_fields or {}).get("load_ratio", 0.0))

    overreaching_flag = int(load_ratio >= 1.2 and recovery_score < 50.0)
    under_recovered_flag = int(rhr_component < 45.0 and hrv_component < 45.0 and sleep_component < 60.0)

    return {
        "readiness_score": round(recovery_score, 2),
        "readiness_confidence": round(confidence, 3),
        "missing_inputs_count": missing_inputs_count,
        "overreaching_flag": overreaching_flag,
        "under_recovered_flag": under_recovered_flag,
        "load_ratio": round(load_ratio, 4),
    }


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
    enable_correlation_matrix: bool,
    enable_zscores: bool,
    enable_trend_signals: bool,
    enable_readiness_flags: bool,
    pipeline_previous_success_epoch: int | None = None,
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

    if enable_correlation_matrix:
        matrix_fields = _derive_correlation_matrix(points, end_date_str)
        if matrix_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived CorrelationMatrix",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": matrix_fields,
                }
            )

    if enable_zscores:
        z_fields = _derive_zscores(points, end_date_str)
        if z_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived ZScores",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": z_fields,
                }
            )

    if enable_trend_signals:
        trend_fields = _derive_trend_signals(points, end_date_str)
        if trend_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived TrendSignals",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": trend_fields,
                }
            )

    if enable_readiness_flags:
        readiness_fields = _derive_readiness_flags(points, end_date_str)
        if readiness_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived ReadinessFlags",
                    "time": metric_time,
                    "tags": {"Device": devicename, "MetricClass": "Derived"},
                    "fields": readiness_fields,
                }
            )

    if enable_pipeline_health:
        now_epoch = int(time.time())
        minutes_since_success = 0.0
        if pipeline_previous_success_epoch is not None:
            minutes_since_success = max(0.0, round((now_epoch - pipeline_previous_success_epoch) / 60.0, 3))
        derived_points.append(
            {
                "measurement": "Derived PipelineHealth",
                "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "tags": {"Device": devicename, "MetricClass": "Derived"},
                "fields": {
                    "last_success_epoch": now_epoch,
                    "minutes_since_success": minutes_since_success,
                    "record_count_last_run": int(len(points)),
                },
            }
        )

    return derived_points
