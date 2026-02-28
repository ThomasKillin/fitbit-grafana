"""Derived metric generation from collected direct records."""

from datetime import datetime
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


def build_derived_points(
    *,
    points,
    devicename: str,
    end_date_str: str,
    enable_pipeline_health: bool,
    enable_recovery_score: bool,
    enable_training_load: bool,
):
    derived_points = []
    metric_time = datetime.fromisoformat(end_date_str + "T00:00:00").isoformat() + "+00:00"

    if enable_training_load:
        daily_load = _derive_daily_load_from_hr_zones(points)
        if daily_load is not None:
            derived_points.append(
                {
                    "measurement": "Derived TrainingLoad",
                    "time": metric_time,
                    "tags": {"Device": devicename},
                    "fields": {
                        "daily_load": round(float(daily_load), 2),
                        "acute_7d": round(float(daily_load), 2),
                        "chronic_28d": round(float(daily_load), 2),
                        "load_ratio": 1.0,
                    },
                }
            )

    if enable_recovery_score:
        recovery_fields = _derive_recovery_score(points)
        if recovery_fields is not None:
            derived_points.append(
                {
                    "measurement": "Derived RecoveryScore",
                    "time": metric_time,
                    "tags": {"Device": devicename},
                    "fields": recovery_fields,
                }
            )

    if enable_pipeline_health:
        derived_points.append(
            {
                "measurement": "Derived PipelineHealth",
                "time": datetime.utcnow().replace(microsecond=0).isoformat() + "+00:00",
                "tags": {"Device": devicename},
                "fields": {
                    "last_success_epoch": int(time.time()),
                    "minutes_since_success": 0.0,
                    "record_count_last_run": int(len(points)),
                },
            }
        )

    return derived_points
