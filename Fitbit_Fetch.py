# %%
import schedule, time, pytz, logging, sys
from datetime import datetime, timedelta, timezone
from fitbit_fetch.collectors_activity import collect_latest_activities, collect_tcx_data
from fitbit_fetch.collectors_basic import collect_battery_level, collect_intraday_data_limit_1d
from fitbit_fetch.collectors_daily import (
    collect_daily_data_limit_30d,
    collect_daily_data_limit_100d,
    collect_daily_data_limit_365d,
    collect_daily_data_limit_none,
)
from fitbit_fetch.collectors_direct import (
    collect_device_sync_health,
    collect_direct_cardio_fitness,
    collect_direct_ecg,
    collect_direct_irn,
)
from fitbit_fetch.config import load_config
from fitbit_fetch.date_utils import build_date_range, refresh_auto_date_range, yield_dates_with_gap
from fitbit_fetch.derived_metrics import build_derived_points
from fitbit_fetch.derived_backfill import (
    DERIVED_BACKFILL_CONTEXT_DAYS,
    DERIVED_BACKFILL_DIRECT_MEASUREMENTS,
    run_derived_startup_auto_backfill,
)
from fitbit_fetch.fitbit_client import FitbitClient, InvalidRefreshTokenError
from fitbit_fetch.influx_writer import InfluxWriter
from fitbit_fetch.metric_classification import annotate_points_with_metric_class
from fitbit_fetch.runner import run_scheduled_auto_update_loop, run_startup_or_bulk_update
from fitbit_fetch.run_utils import build_date_list, write_and_reset_records
from fitbit_fetch.services import AppServices
from fitbit_fetch.state import RuntimeState

# %% [markdown]
# ## Variables

# %%
CONFIG = load_config()
FITBIT_LOG_FILE_PATH = CONFIG.fitbit_log_file_path
TOKEN_FILE_PATH = CONFIG.token_file_path
OVERWRITE_LOG_FILE = CONFIG.overwrite_log_file
FITBIT_LANGUAGE = CONFIG.fitbit_language
FITBIT_RATE_LIMIT_BUFFER_SECONDS = CONFIG.fitbit_rate_limit_buffer_seconds
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
MANUAL_START_DATE = CONFIG.manual_start_date
MANUAL_END_DATE = CONFIG.manual_end_date
AUTO_DATE_RANGE = CONFIG.auto_date_range
auto_update_date_range = CONFIG.auto_update_date_range # Days to go back from today for AUTO_DATE_RANGE *** DO NOT go above 2 - otherwise may break rate limit ***
LOCAL_TIMEZONE = CONFIG.local_timezone # set to "Automatic" for Automatic setup from User profile (if not mentioned here specifically).
SCHEDULE_AUTO_UPDATE = CONFIG.schedule_auto_update # Scheduling updates of data when script runs
SERVER_ERROR_MAX_RETRY = CONFIG.server_error_max_retry
EXPIRED_TOKEN_MAX_RETRY = CONFIG.expired_token_max_retry
SKIP_REQUEST_ON_SERVER_ERROR = CONFIG.skip_request_on_server_error
ENABLE_DERIVED_PIPELINE_HEALTH = CONFIG.enable_derived_pipeline_health
ENABLE_DERIVED_RECOVERY_SCORE = CONFIG.enable_derived_recovery_score
ENABLE_DERIVED_TRAINING_LOAD = CONFIG.enable_derived_training_load
ENABLE_DERIVED_CARDIO_FITNESS = CONFIG.enable_derived_cardio_fitness
ENABLE_DERIVED_CORRELATION_SIGNALS = CONFIG.enable_derived_correlation_signals
ENABLE_DERIVED_CORRELATION_MATRIX = CONFIG.enable_derived_correlation_matrix
ENABLE_DERIVED_ZSCORES = CONFIG.enable_derived_zscores
ENABLE_DERIVED_TREND_SIGNALS = CONFIG.enable_derived_trend_signals
ENABLE_DERIVED_READINESS_FLAGS = CONFIG.enable_derived_readiness_flags
ENABLE_DERIVED_AUTO_BACKFILL = CONFIG.enable_derived_auto_backfill
DERIVED_AUTO_BACKFILL_DAYS = CONFIG.derived_auto_backfill_days
DERIVED_AUTO_BACKFILL_MAX_DAYS_PER_RUN = CONFIG.derived_auto_backfill_max_days_per_run
ENABLE_DIRECT_CARDIO_FITNESS = CONFIG.enable_direct_cardio_fitness
ENABLE_DIRECT_ECG = CONFIG.enable_direct_ecg
ENABLE_DIRECT_IRN = CONFIG.enable_direct_irn
ENABLE_DEVICE_SYNC_HEALTH = CONFIG.enable_device_sync_health
APP_STATE = RuntimeState()
APP_SERVICES = AppServices(
    client_id=CONFIG.client_id,
    client_secret=CONFIG.client_secret,
    devicename=CONFIG.devicename,
)

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
# Generic request caller for all Fitbit endpoints.
def request_data_from_fitbit(url, headers=None, params=None, data=None, request_type="get"):
    if APP_SERVICES.fitbit_client is None:
        raise RuntimeError("Fitbit client is not initialized")
    APP_SERVICES.fitbit_client.access_token = APP_STATE.access_token
    response_data = APP_SERVICES.fitbit_client.request_data(
        url,
        headers=headers,
        params=params,
        data=data,
        request_type=request_type,
    )
    APP_STATE.access_token = APP_SERVICES.fitbit_client.access_token
    return response_data

# %% [markdown]
# ## Token Refresh Management

def Get_New_Access_Token():
    if APP_SERVICES.fitbit_client is None:
        raise RuntimeError("Fitbit client is not initialized")
    access_token = APP_SERVICES.fitbit_client.get_new_access_token(
        APP_SERVICES.client_id,
        APP_SERVICES.client_secret,
    )
    APP_STATE.access_token = access_token
    return access_token

# %% [markdown]
# ## Influxdb Database Initialization

# %%
def write_points_to_influxdb(points):
    if APP_SERVICES.influx_writer is None:
        raise RuntimeError("Influx writer is not initialized")
    direct_points = annotate_points_with_metric_class(points, "Direct")
    derived_input_points = _build_runtime_derived_input_points(direct_points)
    derived_points = build_derived_points(
        points=derived_input_points,
        devicename=APP_SERVICES.devicename,
        end_date_str=APP_STATE.end_date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        enable_pipeline_health=ENABLE_DERIVED_PIPELINE_HEALTH,
        enable_recovery_score=ENABLE_DERIVED_RECOVERY_SCORE,
        enable_training_load=ENABLE_DERIVED_TRAINING_LOAD,
        enable_cardio_fitness=ENABLE_DERIVED_CARDIO_FITNESS,
        enable_correlation_signals=ENABLE_DERIVED_CORRELATION_SIGNALS,
        enable_correlation_matrix=ENABLE_DERIVED_CORRELATION_MATRIX,
        enable_zscores=ENABLE_DERIVED_ZSCORES,
        enable_trend_signals=ENABLE_DERIVED_TREND_SIGNALS,
        enable_readiness_flags=ENABLE_DERIVED_READINESS_FLAGS,
        pipeline_previous_success_epoch=APP_STATE.last_pipeline_success_epoch,
    )
    APP_SERVICES.influx_writer.write_points(direct_points + derived_points)
    APP_STATE.last_pipeline_success_epoch = int(time.time())


def _point_signature(point):
    tags = tuple(sorted((point.get("tags") or {}).items()))
    fields = tuple(sorted((point.get("fields") or {}).items()))
    return (
        point.get("measurement"),
        point.get("time"),
        tags,
        fields,
    )


def _build_runtime_derived_input_points(direct_points):
    end_date_str = APP_STATE.end_date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    context_start_str = (end_date - timedelta(days=DERIVED_BACKFILL_CONTEXT_DAYS - 1)).isoformat()

    try:
        historical_points = APP_SERVICES.influx_writer.fetch_direct_points_for_range(
            start_day_str=context_start_str,
            end_day_str=end_date_str,
            measurements=DERIVED_BACKFILL_DIRECT_MEASUREMENTS,
        )
    except Exception as err:
        logging.warning("Runtime derived context fetch failed, using current batch only: %s", err)
        historical_points = []

    merged = []
    seen = set()
    for point in historical_points + direct_points:
        sig = _point_signature(point)
        if sig in seen:
            continue
        seen.add(sig)
        merged.append(point)
    return merged

def initialize_clients():
    APP_SERVICES.fitbit_client = FitbitClient(
        token_file_path=TOKEN_FILE_PATH,
        fitbit_language=FITBIT_LANGUAGE,
        rate_limit_buffer_seconds=FITBIT_RATE_LIMIT_BUFFER_SECONDS,
        client_id=APP_SERVICES.client_id,
        client_secret=APP_SERVICES.client_secret,
        server_error_max_retry=SERVER_ERROR_MAX_RETRY,
        expired_token_max_retry=EXPIRED_TOKEN_MAX_RETRY,
        skip_request_on_server_error=SKIP_REQUEST_ON_SERVER_ERROR,
        logger=logging,
    )
    APP_SERVICES.influx_writer = InfluxWriter(
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

def initialize_runtime_state():
    try:
        APP_STATE.access_token = Get_New_Access_Token()
    except InvalidRefreshTokenError as err:
        logging.error(str(err))
        print(str(err))
        raise SystemExit(1)

    if LOCAL_TIMEZONE == "Automatic":
        resolved_local_timezone = pytz.timezone(
            request_data_from_fitbit("https://api.fitbit.com/1/user/-/profile.json")["user"]["timezone"]
        )
    else:
        resolved_local_timezone = pytz.timezone(LOCAL_TIMEZONE)
    APP_STATE.local_timezone = resolved_local_timezone

    APP_STATE.start_date, APP_STATE.end_date, APP_STATE.start_date_str, APP_STATE.end_date_str = build_date_range(
        local_timezone=APP_STATE.local_timezone,
        auto_date_range=AUTO_DATE_RANGE,
        auto_update_date_range=auto_update_date_range,
        manual_start_date=MANUAL_START_DATE,
        manual_end_date=MANUAL_END_DATE,
    )

# %% [markdown]
# ## Setting up functions for Requesting data from server

# %%
def get_collected_records():
    return APP_STATE.collected_records

def set_collected_records(records):
    APP_STATE.collected_records = records

def update_working_dates():
    APP_STATE.start_date, APP_STATE.end_date, APP_STATE.start_date_str, APP_STATE.end_date_str = refresh_auto_date_range(
        local_timezone=APP_STATE.local_timezone,
        auto_update_date_range=auto_update_date_range,
    )

# Get last synced battery level of the device
def get_battery_level():
    collect_battery_level(
        request_data_from_fitbit=request_data_from_fitbit,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# For intraday detailed data, max possible range in one day. 
def get_intraday_data_limit_1d(date_str, measurement_list):
    collect_intraday_data_limit_1d(
        request_data_from_fitbit=request_data_from_fitbit,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
        date_str=date_str,
        measurement_list=measurement_list,
    )

# Max range is 30 days, records BR, SPO2 Intraday, skin temp and HRV - 4 queries
def get_daily_data_limit_30d(start_date_str, end_date_str):
    collect_daily_data_limit_30d(
        request_data_from_fitbit=request_data_from_fitbit,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# Only for sleep data - limit 100 days - 1 query
def get_daily_data_limit_100d(start_date_str, end_date_str):
    collect_daily_data_limit_100d(
        request_data_from_fitbit=request_data_from_fitbit,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# Max date range 1 year, records HR zones, Activity minutes and Resting HR - 4 + 3 + 1 + 1 = 9 queries
def get_daily_data_limit_365d(start_date_str, end_date_str):
    collect_daily_data_limit_365d(
        request_data_from_fitbit=request_data_from_fitbit,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# records SPO2 single days for the whole given period - 1 query
def get_daily_data_limit_none(start_date_str, end_date_str):
    collect_daily_data_limit_none(
        request_data_from_fitbit=request_data_from_fitbit,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
        local_timezone=APP_STATE.local_timezone,
        devicename=APP_SERVICES.devicename,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# fetches TCX GPS data
def get_tcx_data(tcx_url, ActivityID):
    collect_tcx_data(
        request_data_from_fitbit=request_data_from_fitbit,
        access_token=APP_STATE.access_token,
        tcx_url=tcx_url,
        activity_id=ActivityID,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

# Fetches latest activities from record ( upto last 50 )
def fetch_latest_activities(end_date_str):
    collect_latest_activities(
        request_data_from_fitbit=request_data_from_fitbit,
        get_tcx_data=get_tcx_data,
        end_date_str=end_date_str,
        collected_records=APP_STATE.collected_records,
        logger=logging,
    )

def get_direct_optional_data(start_date_str, end_date_str):
    if ENABLE_DIRECT_CARDIO_FITNESS:
        collect_direct_cardio_fitness(
            request_data_from_fitbit=request_data_from_fitbit,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            local_timezone=APP_STATE.local_timezone,
            devicename=APP_SERVICES.devicename,
            collected_records=APP_STATE.collected_records,
            logger=logging,
            warning_cache=APP_STATE.optional_endpoint_warnings,
        )
    if ENABLE_DIRECT_ECG:
        collect_direct_ecg(
            request_data_from_fitbit=request_data_from_fitbit,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            local_timezone=APP_STATE.local_timezone,
            devicename=APP_SERVICES.devicename,
            collected_records=APP_STATE.collected_records,
            logger=logging,
            warning_cache=APP_STATE.optional_endpoint_warnings,
        )
    if ENABLE_DIRECT_IRN:
        collect_direct_irn(
            request_data_from_fitbit=request_data_from_fitbit,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            local_timezone=APP_STATE.local_timezone,
            devicename=APP_SERVICES.devicename,
            collected_records=APP_STATE.collected_records,
            logger=logging,
            warning_cache=APP_STATE.optional_endpoint_warnings,
        )
    if ENABLE_DEVICE_SYNC_HEALTH:
        collect_device_sync_health(
            request_data_from_fitbit=request_data_from_fitbit,
            local_timezone=APP_STATE.local_timezone,
            devicename=APP_SERVICES.devicename,
            collected_records=APP_STATE.collected_records,
            logger=logging,
            warning_cache=APP_STATE.optional_endpoint_warnings,
        )


def main():
    initialize_clients()
    initialize_runtime_state()
    run_derived_startup_auto_backfill(
        enabled=ENABLE_DERIVED_AUTO_BACKFILL,
        influx_writer=APP_SERVICES.influx_writer,
        logger=logging,
        devicename=APP_SERVICES.devicename,
        end_date_str=APP_STATE.end_date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        requested_days=DERIVED_AUTO_BACKFILL_DAYS,
        max_days_per_run=DERIVED_AUTO_BACKFILL_MAX_DAYS_PER_RUN,
        enable_recovery_score=ENABLE_DERIVED_RECOVERY_SCORE,
        enable_training_load=ENABLE_DERIVED_TRAINING_LOAD,
        enable_cardio_fitness=ENABLE_DERIVED_CARDIO_FITNESS,
        enable_correlation_signals=ENABLE_DERIVED_CORRELATION_SIGNALS,
        enable_correlation_matrix=ENABLE_DERIVED_CORRELATION_MATRIX,
        enable_zscores=ENABLE_DERIVED_ZSCORES,
        enable_trend_signals=ENABLE_DERIVED_TREND_SIGNALS,
        enable_readiness_flags=ENABLE_DERIVED_READINESS_FLAGS,
        sleep_fn=time.sleep,
    )

    # %% [markdown]
    # ## Call the functions one time as a startup update OR do switch to bulk update mode

    # %%
    run_startup_or_bulk_update(
        auto_date_range=AUTO_DATE_RANGE,
        start_date=APP_STATE.start_date,
        end_date=APP_STATE.end_date,
        start_date_str=APP_STATE.start_date_str,
        end_date_str=APP_STATE.end_date_str,
        schedule_module=schedule,
        logger=logging,
        get_new_access_token=Get_New_Access_Token,
        build_date_list=build_date_list,
        get_intraday_data_limit_1d=get_intraday_data_limit_1d,
        get_daily_data_limit_30d=get_daily_data_limit_30d,
        get_daily_data_limit_100d=get_daily_data_limit_100d,
        get_daily_data_limit_365d=get_daily_data_limit_365d,
        get_daily_data_limit_none=get_daily_data_limit_none,
        get_battery_level=get_battery_level,
        fetch_latest_activities=fetch_latest_activities,
        write_points_to_influxdb=write_points_to_influxdb,
        write_and_reset_records=write_and_reset_records,
        yield_dates_with_gap=yield_dates_with_gap,
        get_collected_records=get_collected_records,
        set_collected_records=set_collected_records,
        get_direct_optional_data=get_direct_optional_data,
    )

    # %% [markdown]
    # ## Schedule functions at specific intervals (Ongoing continuous update)

    # %%
    # Ongoing continuous update of data
    if SCHEDULE_AUTO_UPDATE:
        run_scheduled_auto_update_loop(
            schedule_module=schedule,
            get_new_access_token=Get_New_Access_Token,
            get_intraday_data_limit_1d=get_intraday_data_limit_1d,
            get_battery_level=get_battery_level,
            get_daily_data_limit_30d=get_daily_data_limit_30d,
            get_daily_data_limit_100d=get_daily_data_limit_100d,
            get_daily_data_limit_365d=get_daily_data_limit_365d,
            get_daily_data_limit_none=get_daily_data_limit_none,
            fetch_latest_activities=fetch_latest_activities,
            get_start_date_str=lambda: APP_STATE.start_date_str,
            get_end_date_str=lambda: APP_STATE.end_date_str,
            datetime_cls=datetime,
            timedelta_cls=timedelta,
            get_collected_records=get_collected_records,
            set_collected_records=set_collected_records,
            write_points_to_influxdb=write_points_to_influxdb,
            write_and_reset_records=write_and_reset_records,
            update_working_dates=update_working_dates,
            time_module=time,
            get_direct_optional_data=get_direct_optional_data,
        )


if __name__ == "__main__":
    main()



