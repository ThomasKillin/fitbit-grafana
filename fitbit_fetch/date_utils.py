"""Date range and batching utilities for collection workflows."""

from datetime import datetime, timedelta


def build_date_range(
    *,
    local_timezone,
    auto_date_range: bool,
    auto_update_date_range: int,
    manual_start_date: str | None,
    manual_end_date: str,
    input_fn=input,
):
    if auto_date_range:
        end_date = datetime.now(local_timezone)
        start_date = end_date - timedelta(days=auto_update_date_range)
        end_date_str = end_date.strftime("%Y-%m-%d")
        start_date_str = start_date.strftime("%Y-%m-%d")
    else:
        start_date_str = manual_start_date or input_fn("Enter start date in YYYY-MM-DD format : ")
        end_date_str = manual_end_date or input_fn("Enter end date in YYYY-MM-DD format : ")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    return start_date, end_date, start_date_str, end_date_str


def refresh_auto_date_range(*, local_timezone, auto_update_date_range: int):
    end_date = datetime.now(local_timezone)
    start_date = end_date - timedelta(days=auto_update_date_range)
    end_date_str = end_date.strftime("%Y-%m-%d")
    start_date_str = start_date.strftime("%Y-%m-%d")
    return start_date, end_date, start_date_str, end_date_str


def yield_dates_with_gap(date_list, gap):
    start_index = -1 * gap
    while start_index < len(date_list) - 1:
        start_index = start_index + gap
        end_index = start_index + gap
        if end_index > len(date_list) - 1:
            end_index = len(date_list) - 1
        if start_index > len(date_list) - 1:
            break
        yield (date_list[start_index], date_list[end_index])
