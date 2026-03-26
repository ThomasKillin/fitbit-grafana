"""Low-risk collector functions extracted from the main runner."""

from datetime import datetime

import pytz


def collect_battery_level(*, request_data_from_fitbit, local_timezone, devicename, collected_records, logger):
    device = request_data_from_fitbit("https://api.fitbit.com/1/user/-/devices.json")[0]
    if device is not None:
        collected_records.append(
            {
                "measurement": "DeviceBatteryLevel",
                "time": local_timezone.localize(datetime.fromisoformat(device["lastSyncTime"])).astimezone(pytz.utc).isoformat(),
                "fields": {
                    "value": float(device["batteryLevel"]),
                },
            }
        )
        logger.info("Recorded battery level for " + devicename)
    else:
        logger.error("Recording battery level failed : " + devicename)


def collect_intraday_data_limit_1d(
    *,
    request_data_from_fitbit,
    local_timezone,
    devicename,
    collected_records,
    logger,
    date_str,
    measurement_list,
):
    for measurement in measurement_list:
        data = request_data_from_fitbit(
            "https://api.fitbit.com/1/user/-/activities/"
            + measurement[0]
            + "/date/"
            + date_str
            + "/1d/"
            + measurement[2]
            + ".json"
        )["activities-" + measurement[0] + "-intraday"]["dataset"]
        if data is not None:
            for value in data:
                log_time = datetime.fromisoformat(date_str + "T" + value["time"])
                utc_time = local_timezone.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append(
                    {
                        "measurement": measurement[1],
                        "time": utc_time,
                        "tags": {
                            "Device": devicename,
                        },
                        "fields": {
                            "value": int(value["value"]),
                        },
                    }
                )
            logger.info("Recorded " + measurement[1] + " intraday for date " + date_str)
        else:
            logger.error("Recording failed : " + measurement[1] + " intraday for date " + date_str)
