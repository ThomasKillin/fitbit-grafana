"""Configuration loading for Fitbit fetch service."""

from dataclasses import dataclass
from datetime import datetime
import os


_FALSE_VALUES = {"false", "f", "no", "0"}


@dataclass(frozen=True)
class AppConfig:
    fitbit_log_file_path: str
    token_file_path: str
    overwrite_log_file: bool
    fitbit_language: str
    fitbit_rate_limit_buffer_seconds: int
    influxdb_version: str
    influxdb_host: str
    influxdb_port: str
    influxdb_username: str
    influxdb_password: str
    influxdb_database: str
    influxdb_bucket: str
    influxdb_org: str
    influxdb_token: str
    influxdb_url: str
    influxdb_v3_access_token: str
    client_id: str
    client_secret: str
    devicename: str
    manual_start_date: str | None
    manual_end_date: str
    auto_date_range: bool
    auto_update_date_range: int
    local_timezone: str
    schedule_auto_update: bool
    server_error_max_retry: int
    expired_token_max_retry: int
    skip_request_on_server_error: bool
    enable_derived_pipeline_health: bool
    enable_derived_recovery_score: bool
    enable_derived_training_load: bool
    enable_derived_cardio_fitness: bool
    enable_derived_correlation_signals: bool
    enable_derived_correlation_matrix: bool
    enable_derived_zscores: bool
    enable_derived_trend_signals: bool
    enable_derived_readiness_flags: bool
    enable_derived_auto_backfill: bool
    derived_auto_backfill_days: int
    derived_auto_backfill_max_days_per_run: int
    enable_direct_cardio_fitness: bool
    enable_direct_ecg: bool
    enable_direct_irn: bool
    enable_device_sync_health: bool


def _is_false_env(value: str | None) -> bool:
    return value is not None and value.strip().lower() in _FALSE_VALUES


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return not _is_false_env(value)


def load_config() -> AppConfig:
    influxdb_version = os.environ.get("INFLUXDB_VERSION") or "1"
    assert influxdb_version in ["1", "2", "3"], (
        "Only InfluxDB version 1 or 2 or 3 is allowed - please put either 1 or 2 or 3"
    )

    manual_start_date = os.getenv("MANUAL_START_DATE", None)
    manual_end_date = os.getenv("MANUAL_END_DATE", datetime.today().strftime("%Y-%m-%d"))
    auto_date_range = False if _is_false_env(os.environ.get("AUTO_DATE_RANGE")) else (not bool(manual_start_date))

    return AppConfig(
        fitbit_log_file_path=os.environ.get("FITBIT_LOG_FILE_PATH") or "your/expected/log/file/location/path",
        token_file_path=os.environ.get("TOKEN_FILE_PATH") or "your/expected/token/file/location/path",
        overwrite_log_file=True,
        fitbit_language="en_US",
        fitbit_rate_limit_buffer_seconds=int(os.environ.get("FITBIT_RATE_LIMIT_BUFFER_SECONDS") or 300),
        influxdb_version=influxdb_version,
        influxdb_host=os.environ.get("INFLUXDB_HOST") or "localhost",
        influxdb_port=os.environ.get("INFLUXDB_PORT") or "8086",
        influxdb_username=os.environ.get("INFLUXDB_USERNAME") or "your_influxdb_username",
        influxdb_password=os.environ.get("INFLUXDB_PASSWORD") or "your_influxdb_password",
        influxdb_database=os.environ.get("INFLUXDB_DATABASE") or "your_influxdb_database_name",
        influxdb_bucket=os.environ.get("INFLUXDB_BUCKET") or "your_bucket_name_here",
        influxdb_org=os.environ.get("INFLUXDB_ORG") or "your_org_here",
        influxdb_token=os.environ.get("INFLUXDB_TOKEN") or "your_token_here",
        influxdb_url=os.environ.get("INFLUXDB_URL") or "http://your_url_here:8086",
        influxdb_v3_access_token=os.getenv("INFLUXDB_V3_ACCESS_TOKEN", ""),
        client_id=os.environ.get("CLIENT_ID") or "your_application_client_ID",
        client_secret=os.environ.get("CLIENT_SECRET") or "your_application_client_secret",
        devicename=os.environ.get("DEVICENAME") or "Your_Device_Name",
        manual_start_date=manual_start_date,
        manual_end_date=manual_end_date,
        auto_date_range=auto_date_range,
        auto_update_date_range=1,
        local_timezone=os.environ.get("LOCAL_TIMEZONE") or "Automatic",
        schedule_auto_update=auto_date_range,
        server_error_max_retry=3,
        expired_token_max_retry=5,
        skip_request_on_server_error=True,
        enable_derived_pipeline_health=_env_bool("ENABLE_DERIVED_PIPELINE_HEALTH", True),
        enable_derived_recovery_score=_env_bool("ENABLE_DERIVED_RECOVERY_SCORE", False),
        enable_derived_training_load=_env_bool("ENABLE_DERIVED_TRAINING_LOAD", False),
        enable_derived_cardio_fitness=_env_bool("ENABLE_DERIVED_CARDIO_FITNESS", False),
        enable_derived_correlation_signals=_env_bool("ENABLE_DERIVED_CORRELATION_SIGNALS", False),
        enable_derived_correlation_matrix=_env_bool("ENABLE_DERIVED_CORRELATION_MATRIX", False),
        enable_derived_zscores=_env_bool("ENABLE_DERIVED_ZSCORES", False),
        enable_derived_trend_signals=_env_bool("ENABLE_DERIVED_TREND_SIGNALS", False),
        enable_derived_readiness_flags=_env_bool("ENABLE_DERIVED_READINESS_FLAGS", False),
        enable_derived_auto_backfill=_env_bool("ENABLE_DERIVED_AUTO_BACKFILL", False),
        derived_auto_backfill_days=int(os.environ.get("DERIVED_AUTO_BACKFILL_DAYS") or 30),
        derived_auto_backfill_max_days_per_run=int(os.environ.get("DERIVED_AUTO_BACKFILL_MAX_DAYS_PER_RUN") or 90),
        enable_direct_cardio_fitness=_env_bool("ENABLE_DIRECT_CARDIO_FITNESS", False),
        enable_direct_ecg=_env_bool("ENABLE_DIRECT_ECG", False),
        enable_direct_irn=_env_bool("ENABLE_DIRECT_IRN", False),
        enable_device_sync_health=_env_bool("ENABLE_DEVICE_SYNC_HEALTH", False),
    )
