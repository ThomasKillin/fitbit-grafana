"""Daily range collectors extracted from the main runner."""

from datetime import datetime

import requests
import pytz


def collect_daily_data_limit_none(
    *,
    request_data_from_fitbit,
    start_date_str,
    end_date_str,
    local_timezone,
    devicename,
    collected_records,
    logger,
):
    try:
        data_list = request_data_from_fitbit(
            "https://api.fitbit.com/1/user/-/spo2/date/" + start_date_str + "/" + end_date_str + ".json"
        )
    except requests.exceptions.HTTPError as err:
        logger.error(f"{err}")
        data_list = None
    if data_list is not None:
        for data in data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "SPO2",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "avg": float(data["value"]["avg"]) if data["value"]["avg"] else None,
                        "max": float(data["value"]["max"]) if data["value"]["max"] else None,
                        "min": float(data["value"]["min"]) if data["value"]["min"] else None,
                    },
                }
            )
        logger.info("Recorded Avg SPO2 for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed : Avg SPO2 for date " + start_date_str + " to " + end_date_str)
