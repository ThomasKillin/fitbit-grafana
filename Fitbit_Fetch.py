# %%
import requests, schedule, time, pytz, logging, sys
from datetime import datetime, timedelta
from fitbit_fetch.collectors_activity import collect_latest_activities, collect_tcx_data
from fitbit_fetch.collectors_basic import collect_battery_level, collect_intraday_data_limit_1d
from fitbit_fetch.config import load_config
from fitbit_fetch.date_utils import build_date_range, refresh_auto_date_range, yield_dates_with_gap
from fitbit_fetch.fitbit_client import FitbitClient, InvalidRefreshTokenError
from fitbit_fetch.influx_writer import InfluxWriter

# %% [markdown]
# ## Variables

# %%
CONFIG = load_config()
FITBIT_LOG_FILE_PATH = CONFIG.fitbit_log_file_path
TOKEN_FILE_PATH = CONFIG.token_file_path
OVERWRITE_LOG_FILE = CONFIG.overwrite_log_file
FITBIT_LANGUAGE = CONFIG.fitbit_language
INFLUXDB_VERSION = CONFIG.influxdb_version
INFLUXDB_HOST = CONFIG.influxdb_host
INFLUXDB_PORT = CONFIG.influxdb_port
INFLUXDB_USERNAME = CONFIG.influxdb_username
INFLUXDB_PASSWORD = CONFIG.influxdb_password
INFLUXDB_DATABASE = CONFIG.influxdb_database
INFLUXDB_BUCKET = CONFIG.influxdb_bucket
INFLUXDB_ORG = CONFIG.influxdb_org
INFLUXDB_TOKEN = CONFIG.influxdb_token
INFLUXDB_URL = CONFIG.influxdb_url
INFLUXDB_V3_ACCESS_TOKEN = CONFIG.influxdb_v3_access_token
# MAKE SURE you set the application type to PERSONAL. Otherwise, you won't have access to intraday data series, resulting in 40X errors.
client_id = CONFIG.client_id
client_secret = CONFIG.client_secret
DEVICENAME = CONFIG.devicename
ACCESS_TOKEN = "" # Empty Global variable initialization, will be replaced with a functional access code later using the refresh code
MANUAL_START_DATE = CONFIG.manual_start_date
MANUAL_END_DATE = CONFIG.manual_end_date
AUTO_DATE_RANGE = CONFIG.auto_date_range
auto_update_date_range = CONFIG.auto_update_date_range # Days to go back from today for AUTO_DATE_RANGE *** DO NOT go above 2 - otherwise may break rate limit ***
LOCAL_TIMEZONE = CONFIG.local_timezone # set to "Automatic" for Automatic setup from User profile (if not mentioned here specifically).
SCHEDULE_AUTO_UPDATE = CONFIG.schedule_auto_update # Scheduling updates of data when script runs
SERVER_ERROR_MAX_RETRY = CONFIG.server_error_max_retry
EXPIRED_TOKEN_MAX_RETRY = CONFIG.expired_token_max_retry
SKIP_REQUEST_ON_SERVER_ERROR = CONFIG.skip_request_on_server_error

# %% [markdown]
# ## Logging setup

# %%
if OVERWRITE_LOG_FILE:
    with open(FITBIT_LOG_FILE_PATH, "w"): pass

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(FITBIT_LOG_FILE_PATH, mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

# %% [markdown]
# ## Setting up base API Caller function

# %%
fitbit_client = FitbitClient(
    token_file_path=TOKEN_FILE_PATH,
    fitbit_language=FITBIT_LANGUAGE,
    client_id=client_id,
    client_secret=client_secret,
    server_error_max_retry=SERVER_ERROR_MAX_RETRY,
    expired_token_max_retry=EXPIRED_TOKEN_MAX_RETRY,
    skip_request_on_server_error=SKIP_REQUEST_ON_SERVER_ERROR,
    logger=logging,
)

# Generic request caller for all Fitbit endpoints.
def request_data_from_fitbit(url, headers=None, params=None, data=None, request_type="get"):
    global ACCESS_TOKEN
    fitbit_client.access_token = ACCESS_TOKEN
    response_data = fitbit_client.request_data(
        url,
        headers=headers,
        params=params,
        data=data,
        request_type=request_type,
    )
    ACCESS_TOKEN = fitbit_client.access_token
    return response_data

# %% [markdown]
# ## Token Refresh Management

# %%
def refresh_fitbit_tokens(client_id, client_secret, refresh_token):
    return fitbit_client.refresh_fitbit_tokens(client_id, client_secret, refresh_token)

def load_tokens_from_file():
    return fitbit_client.load_tokens_from_file()

def Get_New_Access_Token(client_id, client_secret):
    global ACCESS_TOKEN
    access_token = fitbit_client.get_new_access_token(client_id, client_secret)
    ACCESS_TOKEN = access_token
    return access_token

try:
    ACCESS_TOKEN = Get_New_Access_Token(client_id, client_secret)
except InvalidRefreshTokenError as err:
    logging.error(str(err))
    print(str(err))
    raise SystemExit(1)

# %% [markdown]
# ## Influxdb Database Initialization

# %%
influx_writer = InfluxWriter(
    version=INFLUXDB_VERSION,
    host=INFLUXDB_HOST,
    port=INFLUXDB_PORT,
    username=INFLUXDB_USERNAME,
    password=INFLUXDB_PASSWORD,
    database=INFLUXDB_DATABASE,
    bucket=INFLUXDB_BUCKET,
    org=INFLUXDB_ORG,
    token=INFLUXDB_TOKEN,
    url=INFLUXDB_URL,
    v3_access_token=INFLUXDB_V3_ACCESS_TOKEN,
    logger=logging,
)

def write_points_to_influxdb(points):
    influx_writer.write_points(points)

# %% [markdown]
# ## Set Timezone from profile data

# %%
if LOCAL_TIMEZONE == "Automatic":
    LOCAL_TIMEZONE = pytz.timezone(request_data_from_fitbit("https://api.fitbit.com/1/user/-/profile.json")["user"]["timezone"])
else:
    LOCAL_TIMEZONE = pytz.timezone(LOCAL_TIMEZONE)

# %% [markdown]
# ## Selecting Dates for update

# %%
start_date, end_date, start_date_str, end_date_str = build_date_range(
    local_timezone=LOCAL_TIMEZONE,
    auto_date_range=AUTO_DATE_RANGE,
    auto_update_date_range=auto_update_date_range,
    manual_start_date=MANUAL_START_DATE,
    manual_end_date=MANUAL_END_DATE,
)

# %% [markdown]
# ## Setting up functions for Requesting data from server

# %%
collected_records = []

def update_working_dates():
    global end_date, start_date, end_date_str, start_date_str
    start_date, end_date, start_date_str, end_date_str = refresh_auto_date_range(
        local_timezone=LOCAL_TIMEZONE,
        auto_update_date_range=auto_update_date_range,
    )

# Get last synced battery level of the device
def get_battery_level():
    collect_battery_level(
        request_data_from_fitbit=request_data_from_fitbit,
        local_timezone=LOCAL_TIMEZONE,
        devicename=DEVICENAME,
        collected_records=collected_records,
        logger=logging,
    )

# For intraday detailed data, max possible range in one day. 
def get_intraday_data_limit_1d(date_str, measurement_list):
    collect_intraday_data_limit_1d(
        request_data_from_fitbit=request_data_from_fitbit,
        local_timezone=LOCAL_TIMEZONE,
        devicename=DEVICENAME,
        collected_records=collected_records,
        logger=logging,
        date_str=date_str,
        measurement_list=measurement_list,
    )

# Max range is 30 days, records BR, SPO2 Intraday, skin temp and HRV - 4 queries
def get_daily_data_limit_30d(start_date_str, end_date_str):

    hrv_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/hrv/date/' + start_date_str + '/' + end_date_str + '.json').get('hrv')
    if hrv_data_list != None:
        for data in hrv_data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                    "measurement":  "HRV",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME
                    },
                    "fields": {
                        "dailyRmssd": float(data["value"]["dailyRmssd"]) if data["value"]["dailyRmssd"] else None,
                        "deepRmssd": float(data["value"]["deepRmssd"]) if data["value"]["deepRmssd"] else None
                    }
                })
        logging.info("Recorded HRV for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed HRV for date " + start_date_str + " to " + end_date_str)

    br_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/br/date/' + start_date_str + '/' + end_date_str + '.json').get("br")
    if br_data_list != None:
        for data in br_data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                    "measurement":  "BreathingRate",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME
                    },
                    "fields": {
                        "value": float(data["value"]["breathingRate"])
                    }
                })
        logging.info("Recorded BR for date " + start_date_str + " to " + end_date_str)
    else:
        logging.warning("Records not found : BR for date " + start_date_str + " to " + end_date_str)

    skin_temp_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/temp/skin/date/' + start_date_str + '/' + end_date_str + '.json').get("tempSkin")
    if skin_temp_data_list != None:
        for temp_record in skin_temp_data_list:
            log_time = datetime.fromisoformat(temp_record["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                    "measurement":  "Skin Temperature Variation",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME
                    },
                    "fields": {
                        "RelativeValue": float(temp_record["value"]["nightlyRelative"])
                    }
                })
        logging.info("Recorded Skin Temperature Variation for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : Skin Temperature Variation for date " + start_date_str + " to " + end_date_str)

    try:
        spo2_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/spo2/date/' + start_date_str + '/' + end_date_str + '/all.json')
    except requests.exceptions.HTTPError as e:
        logging.error(f"{e}")
        spo2_data_list = None
    if spo2_data_list != None:
        for days in spo2_data_list:
            data = days["minutes"]
            for record in data: 
                log_time = datetime.fromisoformat(record["minute"])
                utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append({
                        "measurement":  "SPO2_Intraday",
                        "time": utc_time,
                        "tags": {
                            "Device": DEVICENAME
                        },
                        "fields": {
                            "value": float(record["value"]),
                        }
                    })
        logging.info("Recorded SPO2 intraday for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : SPO2 intraday for date " + start_date_str + " to " + end_date_str)

    weight_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/body/log/weight/date/' + start_date_str + '/' + end_date_str + '.json').get("weight")
    if weight_data_list != None:
        for entry in weight_data_list:
            log_time = datetime.fromisoformat(entry["date"] + "T" + entry["time"])
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                "measurement":  "weight",
                "time": utc_time,
                "tags": {
                    "Device": DEVICENAME
                },
                "fields": {
                    "value": float(entry["weight"]),
                }
            })
            collected_records.append({
                "measurement":  "bmi",
                "time": utc_time,
                "tags": {
                    "Device": DEVICENAME
                },
                "fields": {
                    "value": float(entry["bmi"]),
                }
            })
        logging.info("Recorded weight and BMI for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : weight and BMI for date " + start_date_str + " to " + end_date_str)

# Only for sleep data - limit 100 days - 1 query
def get_daily_data_limit_100d(start_date_str, end_date_str):

    sleep_data = request_data_from_fitbit('https://api.fitbit.com/1.2/user/-/sleep/date/' + start_date_str + '/' + end_date_str + '.json').get("sleep")
    if sleep_data != None:
        for record in sleep_data:
            log_time = datetime.fromisoformat(record["startTime"])
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            try:
                minutesLight= record['levels']['summary']['light']['minutes']
                minutesREM = record['levels']['summary']['rem']['minutes']
                minutesDeep = record['levels']['summary']['deep']['minutes']
            except:
                minutesLight= record['levels']['summary']['asleep']['minutes']
                minutesREM = record['levels']['summary']['restless']['minutes']
                minutesDeep = 0

            collected_records.append({
                    "measurement":  "Sleep Summary",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME,
                        "isMainSleep": record["isMainSleep"],
                    },
                    "fields": {
                        'efficiency': record["efficiency"],
                        'minutesAfterWakeup': record['minutesAfterWakeup'],
                        'minutesAsleep': record['minutesAsleep'],
                        'minutesToFallAsleep': record['minutesToFallAsleep'],
                        'minutesInBed': record['timeInBed'],
                        'minutesAwake': record['minutesAwake'],
                        'minutesLight': minutesLight,
                        'minutesREM': minutesREM,
                        'minutesDeep': minutesDeep
                    }
                })
            
            sleep_level_mapping = {'wake': 3, 'rem': 2, 'light': 1, 'deep': 0, 'asleep': 1, 'restless': 2, 'awake': 3, 'unknown': 4}
            for sleep_stage in record['levels']['data']:
                log_time = datetime.fromisoformat(sleep_stage["dateTime"])
                utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append({
                        "measurement":  "Sleep Levels",
                        "time": utc_time,
                        "tags": {
                            "Device": DEVICENAME,
                            "isMainSleep": record["isMainSleep"],
                        },
                        "fields": {
                            'level': sleep_level_mapping[sleep_stage["level"]],
                            'duration_seconds': sleep_stage["seconds"]
                        }
                    })
            wake_time = datetime.fromisoformat(record["endTime"])
            utc_wake_time = LOCAL_TIMEZONE.localize(wake_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                        "measurement":  "Sleep Levels",
                        "time": utc_wake_time,
                        "tags": {
                            "Device": DEVICENAME,
                            "isMainSleep": record["isMainSleep"],
                        },
                        "fields": {
                            'level': sleep_level_mapping['wake'],
                            'duration_seconds': None
                        }
                    })
        logging.info("Recorded Sleep data for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : Sleep data for date " + start_date_str + " to " + end_date_str)

# Max date range 1 year, records HR zones, Activity minutes and Resting HR - 4 + 3 + 1 + 1 = 9 queries
def get_daily_data_limit_365d(start_date_str, end_date_str):
    activity_minutes_list = ["minutesSedentary", "minutesLightlyActive", "minutesFairlyActive", "minutesVeryActive"]
    for activity_type in activity_minutes_list:
        activity_minutes_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/activities/tracker/' + activity_type + '/date/' + start_date_str + '/' + end_date_str + '.json').get("activities-tracker-"+activity_type)
        if activity_minutes_data_list != None:
            for data in activity_minutes_data_list:
                log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
                utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
                collected_records.append({
                        "measurement": "Activity Minutes",
                        "time": utc_time,
                        "tags": {
                            "Device": DEVICENAME
                        },
                        "fields": {
                            activity_type : int(data["value"])
                        }
                    })
            logging.info("Recorded " + activity_type + "for date " + start_date_str + " to " + end_date_str)
        else:
            logging.error("Recording failed : " + activity_type + " for date " + start_date_str + " to " + end_date_str)
        

    activity_others_list = ["distance", "calories", "steps"]
    for activity_type in activity_others_list:
        activity_others_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/activities/tracker/' + activity_type + '/date/' + start_date_str + '/' + end_date_str + '.json').get("activities-tracker-"+activity_type)
        if activity_others_data_list != None:
            for data in activity_others_data_list:
                log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
                utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
                activity_name = "Total Steps" if activity_type == "steps" else activity_type
                collected_records.append({
                        "measurement": activity_name,
                        "time": utc_time,
                        "tags": {
                            "Device": DEVICENAME
                        },
                        "fields": {
                            "value" : float(data["value"])
                        }
                    })
            logging.info("Recorded " + activity_name + " for date " + start_date_str + " to " + end_date_str)
        else:
            logging.error("Recording failed : " + activity_name + " for date " + start_date_str + " to " + end_date_str)
        

    HR_zones_data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/activities/heart/date/' + start_date_str + '/' + end_date_str + '.json').get("activities-heart")
    if HR_zones_data_list != None:
        for data in HR_zones_data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                    "measurement": "HR zones",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME
                    },
                    # Using get() method with a default value 0 to prevent keyerror ( see issue #31)
                    "fields": {
                        "Normal" : data["value"]["heartRateZones"][0].get("minutes", 0),
                        "Fat Burn" :  data["value"]["heartRateZones"][1].get("minutes", 0),
                        "Cardio" :  data["value"]["heartRateZones"][2].get("minutes", 0),
                        "Peak" :  data["value"]["heartRateZones"][3].get("minutes", 0)
                    }
                })
            if "restingHeartRate" in data["value"]:
                collected_records.append({
                            "measurement":  "RestingHR",
                            "time": utc_time,
                            "tags": {
                                "Device": DEVICENAME
                            },
                            "fields": {
                                "value": data["value"]["restingHeartRate"]
                            }
                        })
        logging.info("Recorded RHR and HR zones for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : RHR and HR zones for date " + start_date_str + " to " + end_date_str)

    HR_zone_minutes_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/activities/active-zone-minutes/date/' + start_date_str + '/' + end_date_str + '.json').get("activities-active-zone-minutes")
    if HR_zone_minutes_list != None:
        for data in HR_zone_minutes_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            if data.get("value"):
                collected_records.append({
                        "measurement": "HR zones",
                        "time": utc_time,
                        "tags": {
                            "Device": DEVICENAME
                        },
                        "fields": data["value"]
                    })
        logging.info("Recorded HR zone minutes for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : HR zone minutes for date " + start_date_str + " to " + end_date_str)

# records SPO2 single days for the whole given period - 1 query
def get_daily_data_limit_none(start_date_str, end_date_str):
    try:
        data_list = request_data_from_fitbit('https://api.fitbit.com/1/user/-/spo2/date/' + start_date_str + '/' + end_date_str + '.json')
    except requests.exceptions.HTTPError as e:
        logging.error(f"{e}")
        data_list = None
    if data_list != None:
        for data in data_list:
            log_time = datetime.fromisoformat(data["dateTime"] + "T" + "00:00:00")
            utc_time = LOCAL_TIMEZONE.localize(log_time).astimezone(pytz.utc).isoformat()
            collected_records.append({
                    "measurement":  "SPO2",
                    "time": utc_time,
                    "tags": {
                        "Device": DEVICENAME
                    },
                    "fields": {
                        "avg": float(data["value"]["avg"]) if data["value"]["avg"] else None,
                        "max": float(data["value"]["max"]) if data["value"]["max"] else None,
                        "min": float(data["value"]["min"]) if data["value"]["min"] else None
                    }
                })
        logging.info("Recorded Avg SPO2 for date " + start_date_str + " to " + end_date_str)
    else:
        logging.error("Recording failed : Avg SPO2 for date " + start_date_str + " to " + end_date_str)

# fetches TCX GPS data
def get_tcx_data(tcx_url, ActivityID):
    collect_tcx_data(
        request_data_from_fitbit=request_data_from_fitbit,
        access_token=ACCESS_TOKEN,
        tcx_url=tcx_url,
        activity_id=ActivityID,
        collected_records=collected_records,
        logger=logging,
    )

# Fetches latest activities from record ( upto last 50 )
def fetch_latest_activities(end_date_str):
    collect_latest_activities(
        request_data_from_fitbit=request_data_from_fitbit,
        get_tcx_data=get_tcx_data,
        end_date_str=end_date_str,
        collected_records=collected_records,
        logger=logging,
    )


# %% [markdown]
# ## Call the functions one time as a startup update OR do switch to bulk update mode

# %%
if AUTO_DATE_RANGE:
    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_date - start_date).days + 1)]
    if len(date_list) > 3:
        logging.warn("Auto schedule update is not meant for more than 3 days at a time, please consider lowering the auto_update_date_range variable to aviod rate limit hit!")
    for date_str in date_list:
        get_intraday_data_limit_1d(date_str, [('heart','HeartRate_Intraday','1sec'),('steps','Steps_Intraday','1min')]) # 2 queries x number of dates ( default 2)
    get_daily_data_limit_30d(start_date_str, end_date_str) # 3 queries
    get_daily_data_limit_100d(start_date_str, end_date_str) # 1 query
    get_daily_data_limit_365d(start_date_str, end_date_str) # 8 queries
    get_daily_data_limit_none(start_date_str, end_date_str) # 1 query
    get_battery_level() # 1 query
    fetch_latest_activities(end_date_str) # 1 query
    write_points_to_influxdb(collected_records)
    collected_records = []
else:
    # Do Bulk update----------------------------------------------------------------------------------------------------------------------------

    schedule.every(1).hours.do(lambda : Get_New_Access_Token(client_id,client_secret)) # Auto-refresh tokens every 1 hour
    
    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_date - start_date).days + 1)]

    def do_bulk_update(funcname, start_date, end_date):
        global collected_records
        funcname(start_date, end_date)
        schedule.run_pending()
        write_points_to_influxdb(collected_records)
        collected_records = []

    fetch_latest_activities(date_list[-1])
    write_points_to_influxdb(collected_records)
    do_bulk_update(get_daily_data_limit_none, date_list[0], date_list[-1])
    for date_range in yield_dates_with_gap(date_list, 360):
        do_bulk_update(get_daily_data_limit_365d, date_range[0], date_range[1])
    for date_range in yield_dates_with_gap(date_list, 98):
        do_bulk_update(get_daily_data_limit_100d, date_range[0], date_range[1])
    for date_range in yield_dates_with_gap(date_list, 28):
        do_bulk_update(get_daily_data_limit_30d, date_range[0], date_range[1])
    for single_day in date_list:
        do_bulk_update(get_intraday_data_limit_1d, single_day, [('heart','HeartRate_Intraday','1sec'),('steps','Steps_Intraday','1min')])

    logging.info("Success : Bulk update complete for " + start_date_str + " to " + end_date_str)
    print("Bulk update complete!")

# %% [markdown]
# ## Schedule functions at specific intervals (Ongoing continuous update)

# %%
# Ongoing continuous update of data
if SCHEDULE_AUTO_UPDATE:
    
    schedule.every(1).hours.do(lambda : Get_New_Access_Token(client_id,client_secret)) # Auto-refresh tokens every 1 hour
    schedule.every(3).minutes.do( lambda : get_intraday_data_limit_1d(end_date_str, [('heart','HeartRate_Intraday','1sec'),('steps','Steps_Intraday','1min')] )) # Auto-refresh detailed HR and steps
    schedule.every(1).hours.do( lambda : get_intraday_data_limit_1d((datetime.strptime(end_date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d"), [('heart','HeartRate_Intraday','1sec'),('steps','Steps_Intraday','1min')] )) # Refilling any missing data on previous day end of night due to fitbit sync delay ( see issue #10 )
    schedule.every(20).minutes.do(get_battery_level) # Auto-refresh battery level
    schedule.every(3).hours.do(lambda : get_daily_data_limit_30d(start_date_str, end_date_str))
    schedule.every(4).hours.do(lambda : get_daily_data_limit_100d(start_date_str, end_date_str))
    schedule.every(6).hours.do( lambda : get_daily_data_limit_365d(start_date_str, end_date_str))
    schedule.every(6).hours.do(lambda : get_daily_data_limit_none(start_date_str, end_date_str))
    schedule.every(1).hours.do( lambda : fetch_latest_activities(end_date_str))

    while True:
        schedule.run_pending()
        if len(collected_records) != 0:
            write_points_to_influxdb(collected_records)
            collected_records = []
        time.sleep(30)
        update_working_dates()
        



