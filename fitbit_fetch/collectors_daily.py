"""Daily range collectors extracted from the main runner."""

from datetime import datetime

import requests
import pytz


def collect_daily_data_limit_30d(
    *,
    request_data_from_fitbit,
    start_date_str,
    end_date_str,
    local_timezone,
    devicename,
    collected_records,
    logger,
):
    hrv_data_list = request_data_from_fitbit(
        "https://api.fitbit.com/1/user/-/hrv/date/" + start_date_str + "/" + end_date_str + ".json"
    ).get("hrv")
    if hrv_data_list is not None:
        for data in hrv_data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "HRV",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "dailyRmssd": float(data["value"]["dailyRmssd"]) if data["value"]["dailyRmssd"] else None,
                        "deepRmssd": float(data["value"]["deepRmssd"]) if data["value"]["deepRmssd"] else None,
                    },
                }
            )
        logger.info("Recorded HRV for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed HRV for date " + start_date_str + " to " + end_date_str)

    br_data_list = request_data_from_fitbit(
        "https://api.fitbit.com/1/user/-/br/date/" + start_date_str + "/" + end_date_str + ".json"
    ).get("br")
    if br_data_list is not None:
        for data in br_data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "BreathingRate",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "value": float(data["value"]["breathingRate"]),
                    },
                }
            )
        logger.info("Recorded BR for date " + start_date_str + " to " + end_date_str)
    else:
        logger.warning("Records not found : BR for date " + start_date_str + " to " + end_date_str)

    skin_temp_data_list = request_data_from_fitbit(
        "https://api.fitbit.com/1/user/-/temp/skin/date/" + start_date_str + "/" + end_date_str + ".json"
    ).get("tempSkin")
    if skin_temp_data_list is not None:
        for temp_record in skin_temp_data_list:
            log_time = datetime.fromisoformat(temp_record["dateTime"] + "T" + "00:00:00")
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "Skin Temperature Variation",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "RelativeValue": float(temp_record["value"]["nightlyRelative"]),
                    },
                }
            )
        logger.info("Recorded Skin Temperature Variation for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed : Skin Temperature Variation for date " + start_date_str + " to " + end_date_str)

    try:
        spo2_data_list = request_data_from_fitbit(
            "https://api.fitbit.com/1/user/-/spo2/date/" + start_date_str + "/" + end_date_str + "/all.json"
        )
    except requests.exceptions.HTTPError as err:
        logger.error(f"{err}")
        spo2_data_list = None
    if spo2_data_list is not None:
        for days in spo2_data_list:
            data = days["minutes"]
            for record in data:
                log_time = datetime.fromisoformat(record["minute"])
                utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append(
                    {
                        "measurement": "SPO2_Intraday",
                        "time": utc_time,
                        "tags": {
                            "Device": devicename,
                        },
                        "fields": {
                            "value": float(record["value"]),
                        },
                    }
                )
        logger.info("Recorded SPO2 intraday for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed : SPO2 intraday for date " + start_date_str + " to " + end_date_str)

    weight_data_list = request_data_from_fitbit(
        "https://api.fitbit.com/1/user/-/body/log/weight/date/" + start_date_str + "/" + end_date_str + ".json"
    ).get("weight")
    if weight_data_list is not None:
        for entry in weight_data_list:
            log_time = datetime.fromisoformat(entry["date"] + "T" + entry["time"])
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "weight",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "value": float(entry["weight"]),
                    },
                }
            )
            collected_records.append(
                {
                    "measurement": "bmi",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                    },
                    "fields": {
                        "value": float(entry["bmi"]),
                    },
                }
            )
        logger.info("Recorded weight and BMI for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed : weight and BMI for date " + start_date_str + " to " + end_date_str)


def collect_daily_data_limit_100d(
    *,
    request_data_from_fitbit,
    start_date_str,
    end_date_str,
    local_timezone,
    devicename,
    collected_records,
    logger,
):
    sleep_data = request_data_from_fitbit(
        "https://api.fitbit.com/1.2/user/-/sleep/date/" + start_date_str + "/" + end_date_str + ".json"
    ).get("sleep")
    if sleep_data is not None:
        for record in sleep_data:
            log_time = datetime.fromisoformat(record["startTime"])
            utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
            try:
                minutes_light = record["levels"]["summary"]["light"]["minutes"]
                minutes_rem = record["levels"]["summary"]["rem"]["minutes"]
                minutes_deep = record["levels"]["summary"]["deep"]["minutes"]
            except Exception:
                minutes_light = record["levels"]["summary"]["asleep"]["minutes"]
                minutes_rem = record["levels"]["summary"]["restless"]["minutes"]
                minutes_deep = 0

            collected_records.append(
                {
                    "measurement": "Sleep Summary",
                    "time": utc_time,
                    "tags": {
                        "Device": devicename,
                        "isMainSleep": record["isMainSleep"],
                    },
                    "fields": {
                        "efficiency": record["efficiency"],
                        "minutesAfterWakeup": record["minutesAfterWakeup"],
                        "minutesAsleep": record["minutesAsleep"],
                        "minutesToFallAsleep": record["minutesToFallAsleep"],
                        "minutesInBed": record["timeInBed"],
                        "minutesAwake": record["minutesAwake"],
                        "minutesLight": minutes_light,
                        "minutesREM": minutes_rem,
                        "minutesDeep": minutes_deep,
                    },
                }
            )

            sleep_level_mapping = {
                "wake": 3,
                "rem": 2,
                "light": 1,
                "deep": 0,
                "asleep": 1,
                "restless": 2,
                "awake": 3,
                "unknown": 4,
            }
            for sleep_stage in record["levels"]["data"]:
                log_time = datetime.fromisoformat(sleep_stage["dateTime"])
                utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append(
                    {
                        "measurement": "Sleep Levels",
                        "time": utc_time,
                        "tags": {
                            "Device": devicename,
                            "isMainSleep": record["isMainSleep"],
                        },
                        "fields": {
                            "level": sleep_level_mapping[sleep_stage["level"]],
                            "duration_seconds": sleep_stage["seconds"],
                        },
                    }
                )
            wake_time = datetime.fromisoformat(record["endTime"])
            utc_wake_time = local_timezone.localize(wake_time).astimezone(pytz.utc).isoformat()
            collected_records.append(
                {
                    "measurement": "Sleep Levels",
                    "time": utc_wake_time,
                    "tags": {
                        "Device": devicename,
                        "isMainSleep": record["isMainSleep"],
                    },
                    "fields": {
                        "level": sleep_level_mapping["wake"],
                        "duration_seconds": None,
                    },
                }
            )
        logger.info("Recorded Sleep data for date " + start_date_str + " to " + end_date_str)
    else:
        logger.error("Recording failed : Sleep data for date " + start_date_str + " to " + end_date_str)


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
