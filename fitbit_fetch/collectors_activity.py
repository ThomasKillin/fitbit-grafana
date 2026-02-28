"""Activity and TCX/GPS collector functions."""

from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

import pytz


def collect_tcx_data(*, request_data_from_fitbit, access_token, tcx_url, activity_id, collected_records, logger):
    tcx_headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/x-www-form-urlencoded",
    }
    tcx_params = {
        "includePartialTCX": "false",
    }
    response = request_data_from_fitbit(tcx_url, headers=tcx_headers, params=tcx_params)
    if response.status_code != 200:
        logger.error(f"Error fetching TCX file: {response.status_code}, {response.text}")
        return

    root = ET.fromstring(response.text)
    namespace = {"ns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
    trackpoints = root.findall(".//ns:Trackpoint", namespace)
    prev_time = None
    prev_distance = None

    for i, trkpt in enumerate(trackpoints):
        time_elem = trkpt.find("ns:Time", namespace)
        lat = trkpt.find(".//ns:LatitudeDegrees", namespace)
        lon = trkpt.find(".//ns:LongitudeDegrees", namespace)
        altitude = trkpt.find("ns:AltitudeMeters", namespace)
        distance = trkpt.find("ns:DistanceMeters", namespace)
        heart_rate = trkpt.find(".//ns:HeartRateBpm/ns:Value", namespace)

        if time_elem is not None and lat is not None:
            current_time = datetime.fromisoformat(time_elem.text.strip("Z"))
            fields = {
                "lat": float(lat.text),
                "lon": float(lon.text),
            }
            if altitude is not None:
                fields["altitude"] = float(altitude.text)
            if distance is not None:
                fields["distance"] = float(distance.text)
                current_distance = float(distance.text)
            else:
                current_distance = None
            if heart_rate is not None:
                fields["heart_rate"] = int(heart_rate.text)
            if i > 0 and prev_time is not None and prev_distance is not None and current_distance is not None:
                time_diff = (current_time - prev_time).total_seconds()
                distance_diff = current_distance - prev_distance
                if time_diff > 0:
                    speed_mps = distance_diff / time_diff
                    speed_kph = speed_mps * 3.6
                    fields["speed_kph"] = speed_kph
            prev_time = current_time
            prev_distance = current_distance

            collected_records.append(
                {
                    "measurement": "GPS",
                    "tags": {
                        "ActivityID": activity_id,
                    },
                    "time": datetime.fromisoformat(time_elem.text.strip("Z")).astimezone(pytz.utc).isoformat(),
                    "fields": fields,
                }
            )


def collect_latest_activities(*, request_data_from_fitbit, get_tcx_data, end_date_str, collected_records, logger):
    next_end_date_str = (datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    recent_activities_data = request_data_from_fitbit(
        "https://api.fitbit.com/1/user/-/activities/list.json",
        params={"beforeDate": next_end_date_str, "sort": "desc", "limit": 50, "offset": 0},
    )
    tcx_record_count, tcx_record_limit = 0, 10
    if recent_activities_data is not None:
        for activity in recent_activities_data["activities"]:
            fields = {}
            if "activeDuration" in activity:
                fields["ActiveDuration"] = int(activity["activeDuration"])
            if "averageHeartRate" in activity:
                fields["AverageHeartRate"] = int(activity["averageHeartRate"])
            if "calories" in activity:
                fields["calories"] = int(activity["calories"])
            if "duration" in activity:
                fields["duration"] = int(activity["duration"])
            if "distance" in activity:
                fields["distance"] = float(activity["distance"])
            if "steps" in activity:
                fields["steps"] = int(activity["steps"])
            starttime = datetime.fromisoformat(activity["startTime"].strip("Z"))
            utc_time = starttime.astimezone(pytz.utc).isoformat()
            try:
                extracted_activity_name = activity["activityName"]
            except KeyError:
                extracted_activity_name = "Unknown-Activity"
            activity_id = utc_time + "-" + extracted_activity_name
            collected_records.append(
                {
                    "measurement": "Activity Records",
                    "time": utc_time,
                    "tags": {
                        "ActivityName": extracted_activity_name,
                    },
                    "fields": fields,
                }
            )
            if activity.get("hasGps", False):
                tcx_link = activity.get("tcxLink", False)
                if tcx_link and tcx_record_count <= tcx_record_limit:
                    tcx_record_count += 1
                    try:
                        get_tcx_data(tcx_link, activity_id)
                        logger.info("Recorded TCX GPS data for " + tcx_link)
                    except Exception as tcx_exception:
                        logger.error("Failed to get GPS Data for " + tcx_link + " : " + str(tcx_exception))
        logger.info("Fetched 50 recent activities before date " + end_date_str)
    else:
        logger.error("Fetching 50 recent activities failed : before date " + end_date_str)
