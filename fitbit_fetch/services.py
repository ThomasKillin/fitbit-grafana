"""Service/dependency container for runtime wiring."""

from dataclasses import dataclass


@dataclass
class AppServices:
    client_id: str
    client_secret: str
    devicename: str
    fitbit_client: object | None = None
    influx_writer: object | None = None
