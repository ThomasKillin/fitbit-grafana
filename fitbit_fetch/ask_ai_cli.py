"""CLI entrypoint for AI text-query over Influx Fitbit data."""

import argparse
import json
import logging
import os
import sys

from fitbit_fetch.ask_ai import answer_question
from fitbit_fetch.config import load_config
from fitbit_fetch.influx_writer import InfluxWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask natural-language questions about Fitbit metrics in InfluxDB.")
    parser.add_argument("--question", required=True, help="Natural language question, e.g. 'How is my recovery score in last 14 days?'")
    parser.add_argument("--window-days", type=int, default=14, help="Default lookback window if question has no explicit range.")
    parser.add_argument("--json", action="store_true", help="Print full JSON response payload.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config()
    logger = logging.getLogger("ask_ai")
    logger.setLevel(logging.INFO)

    influx_writer = InfluxWriter(
        version=config.influxdb_version,
        host=config.influxdb_host,
        port=config.influxdb_port,
        username=config.influxdb_username,
        password=config.influxdb_password,
        database=config.influxdb_database,
        bucket=config.influxdb_bucket,
        org=config.influxdb_org,
        token=config.influxdb_token,
        url=config.influxdb_url,
        v3_access_token=config.influxdb_v3_access_token,
        logger=logger,
    )

    try:
        result = answer_question(
            question=args.question,
            influx_writer=influx_writer,
            default_window_days=max(1, args.window_days),
            ai_provider=os.getenv("AI_PROVIDER", "auto"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            ollama_base_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        )
    except Exception as err:
        print(f"Ask AI query failed: {err}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    elif result.get("ok"):
        print(result["answer"])
    else:
        print(result.get("error", "Unknown error"))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
