"""InfluxDB initialization and write wrapper."""

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from influxdb_client import InfluxDBClient as InfluxDBClient2
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client_3 import InfluxDBClient3, InfluxDBError


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

        if self.version == "2":
            try:
                self._client = InfluxDBClient2(url=url, token=token, org=org)
                self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            except InfluxDBError as err:
                self.logger.error("Unable to connect with influxdb 2.x database! Aborted")
                raise InfluxDBError("InfluxDB connection failed:" + str(err))
        elif self.version == "1":
            try:
                self._client = InfluxDBClient(host=host, port=port, username=username, password=password)
                self._client.switch_database(database)
            except InfluxDBClientError as err:
                self.logger.error("Unable to connect with influxdb 1.x database! Aborted")
                raise InfluxDBClientError("InfluxDB connection failed:" + str(err))
        elif self.version == "3":
            try:
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
            except InfluxDBError as err:
                self.logger.error("Unable to connect with influxdb 3.x database! Aborted")
                raise InfluxDBClientError("InfluxDB connection failed:" + str(err))
        else:
            self.logger.error("No matching version found. Supported values are 1 and 2 and 3")
            raise InfluxDBClientError("No matching version found. Supported values are 1 and 2 and 3")

    def write_points(self, points) -> None:
        if self.version == "2":
            try:
                self._write_api.write(bucket=self.bucket, org=self.org, record=points)
                self.logger.info("Successfully updated influxdb database with new points")
            except InfluxDBError as err:
                self.logger.error("Unable to connect with influxdb 2.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        elif self.version == "1":
            try:
                self._client.write_points(points)
                self.logger.info("Successfully updated influxdb database with new points")
            except InfluxDBClientError as err:
                self.logger.error("Unable to connect with influxdb 1.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        elif self.version == "3":
            try:
                self._client.write(record=points)
                self.logger.info("Successfully updated influxdb database with new points")
            except InfluxDBError as err:
                self.logger.error("Unable to connect with influxdb 3.x database! " + str(err))
                print("Influxdb connection failed! ", str(err))
        else:
            self.logger.error("No matching version found. Supported values are 1 and 2 and 3")
            raise InfluxDBClientError("No matching version found. Supported values are 1 and 2 and 3")
