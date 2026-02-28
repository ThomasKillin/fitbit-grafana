"""Mutable runtime state container for the Fitbit fetch app."""

from dataclasses import dataclass, field


@dataclass
class RuntimeState:
    access_token: str = ""
    local_timezone: object | None = None
    start_date: object | None = None
    end_date: object | None = None
    start_date_str: str = ""
    end_date_str: str = ""
    collected_records: list = field(default_factory=list)
