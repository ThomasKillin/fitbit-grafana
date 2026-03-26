"""CLI for checking optional Fitbit endpoint availability."""

import argparse
import json
import logging
import sys

from fitbit_fetch.config import load_config
from fitbit_fetch.endpoint_capability import OPTIONAL_ENDPOINTS, check_endpoint_support, default_date_window
from fitbit_fetch.fitbit_client import FitbitClient, InvalidRefreshTokenError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check availability of optional Fitbit endpoints (CardioFitness, ECG, IRN, DeviceSyncHealth)."
    )
    parser.add_argument("--start-date", default=None, help="Start date YYYY-MM-DD (defaults to 14-day window).")
    parser.add_argument("--end-date", default=None, help="End date YYYY-MM-DD (defaults to today).")
    parser.add_argument("--json", action="store_true", help="Print full JSON result.")
    return parser


def _print_table(results: list[dict]) -> None:
    headers = ("Endpoint", "Status", "HTTP", "Detail")
    rows = []
    for row in results:
        rows.append(
            (
                str(row.get("endpoint", "")),
                str(row.get("status", "")),
                str(row.get("http_status", "")),
                str(row.get("detail", "")),
            )
        )
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    def fmt(values):
        return " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values))

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))


def main() -> int:
    args = build_parser().parse_args()
    config = load_config()

    logger = logging.getLogger("endpoint_capability")
    logger.setLevel(logging.INFO)

    fitbit_client = FitbitClient(
        token_file_path=config.token_file_path,
        fitbit_language=config.fitbit_language,
        rate_limit_buffer_seconds=config.fitbit_rate_limit_buffer_seconds,
        client_id=config.client_id,
        client_secret=config.client_secret,
        server_error_max_retry=config.server_error_max_retry,
        expired_token_max_retry=config.expired_token_max_retry,
        skip_request_on_server_error=config.skip_request_on_server_error,
        logger=logger,
    )

    try:
        access_token = fitbit_client.get_new_access_token(config.client_id, config.client_secret)
    except InvalidRefreshTokenError as err:
        print(str(err))
        return 1
    except Exception as err:
        print(f"Token refresh failed: {err}")
        return 1

    fitbit_client.access_token = access_token

    if args.start_date and args.end_date:
        start_date, end_date = args.start_date, args.end_date
    else:
        start_date, end_date = default_date_window(14)
        if args.start_date:
            start_date = args.start_date
        if args.end_date:
            end_date = args.end_date

    def request_data_from_fitbit(url):
        return fitbit_client.request_data(url)

    results = [
        check_endpoint_support(
            spec=spec,
            start_date=start_date,
            end_date=end_date,
            request_data_from_fitbit=request_data_from_fitbit,
        )
        for spec in OPTIONAL_ENDPOINTS
    ]

    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Endpoint capability check window: {start_date} to {end_date}")
        _print_table(results)

    return 2 if any(row.get("status") == "error" for row in results) else 0


if __name__ == "__main__":
    sys.exit(main())

