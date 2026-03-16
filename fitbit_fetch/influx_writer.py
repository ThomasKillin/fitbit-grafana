"""InfluxDB initialization and write wrapper."""

from datetime import datetime, timedelta, timezone
import os
import sys


class InfluxWriterError(Exception):
    """Local wrapper error for optional InfluxDB client imports."""


def _safe_import_influxdb_v1():
    try:
        from influxdb import InfluxDBClient as _InfluxDBClient
        from influxdb.exceptions import InfluxDBClientError as _InfluxDBClientError
        return _InfluxDBClient, _InfluxDBClientError
    except Exception:
        # Avoid local repo/data folder shadowing (e.g., ./influxdb) when importing the package.
        original_sys_path = list(sys.path)
        try:
            pruned = []
            for path in original_sys_path:
                local_influx_path = os.path.join(path, "influxdb")
                if os.path.isdir(local_influx_path) and not os.path.isfile(os.path.join(local_influx_path, "__init__.py")):
                    continue
                pruned.append(path)
            sys.path = pruned
            # Clear potentially shadowed namespace package from the first failed import.
            sys.modules.pop("influxdb", None)
            from influxdb import InfluxDBClient as _InfluxDBClient
            from influxdb.exceptions import InfluxDBClientError as _InfluxDBClientError
            return _InfluxDBClient, _InfluxDBClientError
        except Exception as err:
            raise InfluxWriterError(
                "InfluxDB v1 client import failed. Install package 'influxdb' "
                "and ensure local ./influxdb folder is not shadowing the module."
            ) from err
        finally:
            sys.path = original_sys_path


InfluxDBClientError = InfluxWriterError


class InfluxWriter:
    def __init__(
        self,
        *,
        version: str,
        host: str,
        port: str,
        username: str,
        password: str,
        database: str,
        bucket: str,
        org: str,
        token: str,
        url: str,
        v3_access_token: str,
        logger,
    ) -> None:
        self.version = version
        self.bucket = bucket
        self.org = org
        self.logger = logger
        self._client = None
        self._write_api = None
        self._v1_error_cls = InfluxWriterError
        self._v2_error_cls = InfluxWriterError
        self._v3_error_cls = InfluxWriterError

        if self.version == "2":
            try:
                from influxdb_client import InfluxDBClient as InfluxDBClient2
                from influxdb_client.client.write_api import SYNCHRONOUS

                self._v2_error_cls = Exception
                self._client = InfluxDBClient2(url=url, token=token, org=org)
                self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            except Exception as err:
                self.logger.error("Unable to connect with influxdb 2.x database! Aborted")
                raise InfluxWriterError("InfluxDB v2 connection failed: " + str(err))
        elif self.version == "1":
            try:
                InfluxDBClient, v1_error_cls = _safe_import_influxdb_v1()
                self._v1_error_cls = v1_error_cls
                self._client = InfluxDBClient(host=host, port=port, username=username, password=password)
                self._client.switch_database(database)
            except Exception as err:
                self.logger.error("Unable to connect with influxdb 1.x database! Aborted")
                raise InfluxWriterError("InfluxDB v1 connection failed: " + str(err))
        elif self.version == "3":
            try:
                from influxdb_client_3 import InfluxDBClient3

                self._v3_error_cls = Exception
                self._client = InfluxDBClient3(
                    host=f"http://{host}:{port}",
                    token=v3_access_token,
                    database=database,
                )
                demo_point = {
                    "measurement": "DemoPoint",
                    "time": "1970-01-01T00:00:00+00:00",
                    "tags": {"DemoTag": "DemoTagValue"},
                    "fields": {"DemoField": 0},
                }
                # Write a static point to fail early if auth/connection is wrong.
                self._client.write(record=[demo_point])
            except Exception as err:
                self.logger.error("Unable to connect with influxdb 3.x database! Aborted")
                raise InfluxWriterError("InfluxDB v3 connection failed: " + str(err))
        else:
            self.logger.error("No matching version found. Supported values are 1 and 2 and 3")
            raise InfluxWriterError("No matching version found. Supported values are 1 and 2 and 3")

    def write_points(self, points) -> None:
        if self.version == "2":
            try:
                self._write_api.write(bucket=self.bucket, org=self.org, record=points)
                self.logger.info("Successfully updated influxdb database with new points")
            except self._v2_error_cls as err:
                self.logger.error("Unable to connect with influxdb 2.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        elif self.version == "1":
            try:
                self._client.write_points(points)
                self.logger.info("Successfully updated influxdb database with new points")
            except self._v1_error_cls as err:
                self.logger.error("Unable to connect with influxdb 1.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        elif self.version == "3":
            try:
                self._client.write(record=points)
                self.logger.info("Successfully updated influxdb database with new points")
            except self._v3_error_cls as err:
                self.logger.error("Unable to connect with influxdb 3.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        else:
            self.logger.error("No matching version found. Supported values are 1 and 2 and 3")
            raise InfluxWriterError("No matching version found. Supported values are 1 and 2 and 3")

    def fetch_direct_points_for_day(self, day_str: str, measurements: list[str]) -> list[dict]:
        """Fetch direct points for a single UTC day window."""
        return self.fetch_direct_points_for_range(
            start_day_str=day_str,
            end_day_str=day_str,
            measurements=measurements,
        )

    def fetch_direct_points_for_range(
        self,
        *,
        start_day_str: str,
        end_day_str: str,
        measurements: list[str],
    ) -> list[dict]:
        """Fetch direct points for an inclusive UTC date range for selected measurements."""
        if not measurements:
            return []

        day_start = datetime.strptime(start_day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_day = datetime.strptime(end_day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_day < day_start:
            return []
        day_end = end_day + timedelta(days=1)
        start_iso = day_start.isoformat().replace("+00:00", "Z")
        end_iso = day_end.isoformat().replace("+00:00", "Z")

        if self.version == "1":
            return self._fetch_direct_points_v1(start_iso=start_iso, end_iso=end_iso, measurements=measurements)
        if self.version == "2":
            return self._fetch_direct_points_v2(start_iso=start_iso, end_iso=end_iso, measurements=measurements)

        self.logger.warning("Derived auto-backfill only supports InfluxDB v1/v2 currently")
        return []

    def _fetch_direct_points_v1(self, *, start_iso: str, end_iso: str, measurements: list[str]) -> list[dict]:
        points = []
        for measurement in measurements:
            query = (
                f'SELECT * FROM "{measurement}" '
                f"WHERE time >= '{start_iso}' AND time < '{end_iso}' AND \"MetricClass\"='Direct'"
            )
            result = self._client.query(query)
            for row in result.get_points(measurement=measurement):
                tags = {}
                fields = {}
                for key, value in row.items():
                    if key == "time" or value is None:
                        continue
                    if key in {"Device", "MetricClass"}:
                        tags[key] = str(value)
                        continue
                    fields[key] = value
                if fields:
                    points.append(
                        {
                            "measurement": measurement,
                            "time": row.get("time"),
                            "tags": tags,
                            "fields": fields,
                        }
                    )
        return points

    def _fetch_direct_points_v2(self, *, start_iso: str, end_iso: str, measurements: list[str]) -> list[dict]:
        measurement_filter = " or ".join([f'r._measurement == "{m}"' for m in measurements])
        query = (
            f'from(bucket: "{self.bucket}")\n'
            f"  |> range(start: time(v: \"{start_iso}\"), stop: time(v: \"{end_iso}\"))\n"
            f"  |> filter(fn: (r) => {measurement_filter})\n"
            "  |> filter(fn: (r) => r.MetricClass == \"Direct\")\n"
            "  |> pivot(rowKey:[\"_time\",\"_measurement\",\"Device\",\"MetricClass\"], columnKey:[\"_field\"], valueColumn:\"_value\")"
        )
        tables = self._client.query_api().query(org=self.org, query=query)
        points = []
        for table in tables:
            for record in table.records:
                values = record.values
                measurement = values.get("_measurement")
                timestamp = values.get("_time")
                if measurement is None or timestamp is None:
                    continue

                tags = {}
                fields = {}
                for key, value in values.items():
                    if key.startswith("_") or key in {"result", "table", "_start", "_stop"} or value is None:
                        continue
                    if key in {"Device", "MetricClass"}:
                        tags[key] = str(value)
                    else:
                        fields[key] = value

                if fields:
                    points.append(
                        {
                            "measurement": measurement,
                            "time": timestamp.isoformat(),
                            "tags": tags,
                            "fields": fields,
                        }
                    )
        return points

    def query_metric_series(
        self,
        *,
        measurement: str,
        field: str,
        days: int,
        metric_class: str | None = None,
    ) -> list[dict]:
        """Query daily mean series for one measurement/field pair."""
        if self.version == "1":
            return self._query_metric_series_v1(
                measurement=measurement,
                field=field,
                days=days,
                metric_class=metric_class,
            )
        if self.version == "2":
            return self._query_metric_series_v2(
                measurement=measurement,
                field=field,
                days=days,
                metric_class=metric_class,
            )
        raise InfluxWriterError("query_metric_series currently supports only InfluxDB v1/v2")

    def _query_metric_series_v1(
        self,
        *,
        measurement: str,
        field: str,
        days: int,
        metric_class: str | None,
    ) -> list[dict]:
        where = f"time >= now() - {int(days)}d"
        if metric_class:
            where += f" AND \"MetricClass\"='{metric_class}'"
        query = (
            f'SELECT mean("{field}") AS value FROM "{measurement}" '
            f"WHERE {where} GROUP BY time(1d) fill(null)"
        )
        result = self._client.query(query)
        rows = []
        for point in result.get_points(measurement=measurement):
            value = point.get("value")
            if value is None:
                continue
            rows.append({"time": point.get("time"), "value": float(value)})
        return rows

    def _query_metric_series_v2(
        self,
        *,
        measurement: str,
        field: str,
        days: int,
        metric_class: str | None,
    ) -> list[dict]:
        metric_filter = ""
        if metric_class:
            metric_filter = f'\n  |> filter(fn: (r) => r.MetricClass == "{metric_class}")'
        query = (
            f'from(bucket: "{self.bucket}")\n'
            f"  |> range(start: -{int(days)}d)\n"
            f'  |> filter(fn: (r) => r._measurement == "{measurement}")\n'
            f'  |> filter(fn: (r) => r._field == "{field}")'
            f"{metric_filter}\n"
            "  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)\n"
            "  |> keep(columns: [\"_time\", \"_value\"])"
        )
        tables = self._client.query_api().query(org=self.org, query=query)
        rows = []
        for table in tables:
            for record in table.records:
                value = record.values.get("_value")
                ts = record.values.get("_time")
                if value is None or ts is None:
                    continue
                rows.append({"time": ts.isoformat(), "value": float(value)})
        return rows
