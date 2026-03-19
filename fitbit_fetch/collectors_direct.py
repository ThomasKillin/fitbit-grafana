"""Collectors for optional direct metrics (best-effort Fitbit endpoints)."""

from datetime import datetime, timedelta

import pytz
import requests


def _warn_once(logger, warning_cache: set[str], key: str, message: str) -> None:
    if key in warning_cache:
        return
    warning_cache.add(key)
    logger.warning(message)


def _safe_request_json(
    *,
    request_data_from_fitbit,
    url: str,
    logger,
    warning_cache: set[str],
    warning_key: str,
) -> dict | list | None:
    try:
        return request_data_from_fitbit(url)
    except requests.exceptions.HTTPError as err:
        status_code = getattr(getattr(err, "response", None), "status_code", None)
        if status_code in {403, 404}:
            _warn_once(
                logger,
                warning_cache,
                warning_key,
                f"Optional endpoint unavailable ({status_code}) for {warning_key}; skipping.",
            )
            return None
        raise


def _to_utc_iso(local_timezone, naive_or_iso: str, default_suffix: str = "T00:00:00") -> str:
    raw = naive_or_iso if "T" in naive_or_iso else naive_or_iso + default_suffix
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = local_timezone.localize(parsed)
    return parsed.astimezone(pytz.utc).isoformat()


def _iter_date_chunks(start_date_str: str, end_date_str: str, max_days_per_chunk: int):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    if end_date < start_date:
        return
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=max_days_per_chunk - 1), end_date)
        yield cursor.isoformat(), chunk_end.isoformat()
        cursor = chunk_end + timedelta(days=1)


def collect_direct_cardio_fitness(
    *,
    request_data_from_fitbit,
    start_date_str: str,
    end_date_str: str,
    local_timezone,
    devicename: str,
    collected_records: list,
    logger,
    warning_cache: set[str],
) -> None:
    written = 0
    # Fitbit cardioscore endpoint accepts max 30-day ranges.
    for chunk_start, chunk_end in _iter_date_chunks(start_date_str, end_date_str, 30):
        payload = _safe_request_json(
            request_data_from_fitbit=request_data_from_fitbit,
            url=f"https://api.fitbit.com/1/user/-/cardioscore/date/{chunk_start}/{chunk_end}.json",
            logger=logger,
            warning_cache=warning_cache,
            warning_key="cardiofitness",
        )
        if payload is None:
            continue

        records = payload.get("cardioScore", []) if isinstance(payload, dict) else []
        for row in records:
            date_key = row.get("dateTime") or row.get("date")
            if not date_key:
                continue
            value_blob = row.get("value", row)
            vo2_max = (
                value_blob.get("vo2Max")
                if isinstance(value_blob, dict)
                else None
            )
            if vo2_max is None and isinstance(value_blob, dict):
                levels = value_blob.get("vo2MaxLevel")
                if isinstance(levels, dict):
                    vo2_max = levels.get("vo2Max")
            if vo2_max is None:
                continue

            collected_records.append(
                {
                    "measurement": "CardioFitness",
                    "time": _to_utc_iso(local_timezone, str(date_key)),
                    "tags": {"Device": devicename},
                    "fields": {"vo2_max": float(vo2_max)},
                }
            )
            written += 1

    if written:
        logger.info("Recorded CardioFitness for date %s to %s", start_date_str, end_date_str)


def collect_direct_ecg(
    *,
    request_data_from_fitbit,
    start_date_str: str,
    end_date_str: str,
    local_timezone,
    devicename: str,
    collected_records: list,
    logger,
    warning_cache: set[str],
) -> None:
    payload = _safe_request_json(
        request_data_from_fitbit=request_data_from_fitbit,
        url=f"https://api.fitbit.com/1/user/-/ecg/list/date/{start_date_str}/{end_date_str}.json",
        logger=logger,
        warning_cache=warning_cache,
        warning_key="ecg",
    )
    if payload is None:
        return

    rows = []
    if isinstance(payload, dict):
        rows = payload.get("ecgReadings") or payload.get("ecg") or payload.get("items") or []
    if not isinstance(rows, list):
        return

    written = 0
    for row in rows:
        timestamp = row.get("startTime") or row.get("dateTime") or row.get("timestamp")
        if not timestamp:
            continue
        classification = (
            row.get("classification")
            or row.get("resultClassification")
            or row.get("rhythm")
            or "unknown"
        )
        avg_hr = row.get("averageHeartRate") or row.get("avgHeartRate")
        duration_ms = row.get("durationMs") or row.get("duration")
        fields = {"event_count": 1.0}
        if avg_hr is not None:
            fields["avg_heart_rate"] = float(avg_hr)
        if duration_ms is not None:
            fields["duration_ms"] = float(duration_ms)
        collected_records.append(
            {
                "measurement": "ECG",
                "time": _to_utc_iso(local_timezone, str(timestamp)),
                "tags": {"Device": devicename, "classification": str(classification)},
                "fields": fields,
            }
        )
        written += 1

    if written:
        logger.info("Recorded ECG events for date %s to %s", start_date_str, end_date_str)


def collect_direct_irn(
    *,
    request_data_from_fitbit,
    start_date_str: str,
    end_date_str: str,
    local_timezone,
    devicename: str,
    collected_records: list,
    logger,
    warning_cache: set[str],
) -> None:
    payload = _safe_request_json(
        request_data_from_fitbit=request_data_from_fitbit,
        url=f"https://api.fitbit.com/1/user/-/irn/list/date/{start_date_str}/{end_date_str}.json",
        logger=logger,
        warning_cache=warning_cache,
        warning_key="irn",
    )
    if payload is None:
        return

    rows = []
    if isinstance(payload, dict):
        rows = payload.get("irnAlerts") or payload.get("irn") or payload.get("items") or []
    if not isinstance(rows, list):
        return

    written = 0
    for row in rows:
        timestamp = row.get("dateTime") or row.get("startTime") or row.get("timestamp")
        if not timestamp:
            continue
        event_type = (
            row.get("result")
            or row.get("status")
            or row.get("alertType")
            or "detected"
        )
        fields = {"event_count": 1.0}
        if row.get("confidence") is not None:
            fields["confidence"] = float(row["confidence"])
        collected_records.append(
            {
                "measurement": "IRN",
                "time": _to_utc_iso(local_timezone, str(timestamp)),
                "tags": {"Device": devicename, "event_type": str(event_type)},
                "fields": fields,
            }
        )
        written += 1

    if written:
        logger.info("Recorded IRN events for date %s to %s", start_date_str, end_date_str)


def collect_device_sync_health(
    *,
    request_data_from_fitbit,
    local_timezone,
    devicename: str,
    collected_records: list,
    logger,
    warning_cache: set[str],
) -> None:
    payload = _safe_request_json(
        request_data_from_fitbit=request_data_from_fitbit,
        url="https://api.fitbit.com/1/user/-/devices.json",
        logger=logger,
        warning_cache=warning_cache,
        warning_key="device_sync_health",
    )
    if payload is None or not isinstance(payload, list):
        return

    for device in payload:
        last_sync = device.get("lastSyncTime")
        if not last_sync:
            continue
        sync_ts = datetime.fromisoformat(last_sync)
        if sync_ts.tzinfo is None:
            sync_ts = local_timezone.localize(sync_ts)
        sync_utc = sync_ts.astimezone(pytz.utc)
        now_utc = datetime.now(pytz.utc)
        minutes_since_sync = max(0.0, (now_utc - sync_utc).total_seconds() / 60.0)
        battery_level = device.get("batteryLevel")
        fields = {
            "minutes_since_last_sync": round(minutes_since_sync, 3),
            "sync_success": 1.0 if minutes_since_sync <= 360 else 0.0,
        }
        if battery_level is not None:
            fields["battery_level"] = float(battery_level)

        collected_records.append(
            {
                "measurement": "DeviceSyncHealth",
                "time": sync_utc.isoformat(),
                "tags": {
                    "Device": devicename,
                    "device_version": str(device.get("deviceVersion", "unknown")),
                    "type": str(device.get("type", "unknown")),
                },
                "fields": fields,
            }
        )

    logger.info("Recorded DeviceSyncHealth for %s", devicename)
