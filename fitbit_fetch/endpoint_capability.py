"""Capability checks for optional Fitbit endpoints."""

from dataclasses import dataclass
from datetime import date, timedelta

import requests


@dataclass(frozen=True)
class EndpointSpec:
    name: str
    url_template: str


OPTIONAL_ENDPOINTS = (
    EndpointSpec("CardioFitness", "https://api.fitbit.com/1/user/-/cardioscore/date/{start}/{end}.json"),
    EndpointSpec("ECG", "https://api.fitbit.com/1/user/-/ecg/list/date/{start}/{end}.json"),
    EndpointSpec("IRN", "https://api.fitbit.com/1/user/-/irn/list/date/{start}/{end}.json"),
    EndpointSpec("DeviceSyncHealth", "https://api.fitbit.com/1/user/-/devices.json"),
)


def default_date_window(days: int = 14) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    return start.isoformat(), end.isoformat()


def _payload_hint(payload) -> str:
    if payload is None:
        return "No payload"
    if isinstance(payload, list):
        return f"List payload ({len(payload)} items)"
    if isinstance(payload, dict):
        keys = sorted(payload.keys())
        sample = ", ".join(keys[:4])
        suffix = "..." if len(keys) > 4 else ""
        return f"Object payload ({sample}{suffix})"
    return f"Payload type: {type(payload).__name__}"


def check_endpoint_support(*, spec: EndpointSpec, start_date: str, end_date: str, request_data_from_fitbit) -> dict:
    url = spec.url_template.format(start=start_date, end=end_date)
    try:
        payload = request_data_from_fitbit(url)
        return {
            "endpoint": spec.name,
            "supported": True,
            "status": "supported",
            "http_status": 200,
            "url": url,
            "detail": _payload_hint(payload),
        }
    except requests.exceptions.HTTPError as err:
        status_code = getattr(getattr(err, "response", None), "status_code", None)
        if status_code in {403, 404}:
            return {
                "endpoint": spec.name,
                "supported": False,
                "status": "unavailable",
                "http_status": status_code,
                "url": url,
                "detail": "Unavailable for current account/scope/region",
            }
        return {
            "endpoint": spec.name,
            "supported": False,
            "status": "error",
            "http_status": status_code,
            "url": url,
            "detail": str(err),
        }
    except Exception as err:
        return {
            "endpoint": spec.name,
            "supported": False,
            "status": "error",
            "http_status": None,
            "url": url,
            "detail": str(err),
        }

