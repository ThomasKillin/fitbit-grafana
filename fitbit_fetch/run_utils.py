"""Runtime orchestration utility helpers."""

from datetime import timedelta


def build_date_list(start_date, end_date):
    return [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((end_date - start_date).days + 1)]


def write_and_reset_records(write_points_to_influxdb, collected_records):
    write_points_to_influxdb(collected_records)
    return []
