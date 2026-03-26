"""Fitbit API client with token refresh and retry behavior."""

import base64
import json
import time

import requests
from requests.exceptions import ConnectionError


class InvalidRefreshTokenError(Exception):
    """Raised when Fitbit rejects the refresh token with invalid_grant."""


class FitbitClient:
    def __init__(
        self,
        *,
        token_file_path: str,
        fitbit_language: str,
        rate_limit_buffer_seconds: int,
        client_id: str,
        client_secret: str,
        server_error_max_retry: int,
        expired_token_max_retry: int,
        skip_request_on_server_error: bool,
        logger,
    ) -> None:
        self.token_file_path = token_file_path
        self.fitbit_language = fitbit_language
        self.rate_limit_buffer_seconds = rate_limit_buffer_seconds
        self.client_id = client_id
        self.client_secret = client_secret
        self.server_error_max_retry = server_error_max_retry
        self.expired_token_max_retry = expired_token_max_retry
        self.skip_request_on_server_error = skip_request_on_server_error
        self.logger = logger
        self.access_token = ""

    def request_data(self, url, headers=None, params=None, data=None, request_type="get"):
        retry_attempts = 0
        headers = headers or {}
        params = params or {}
        data = data or {}

        self.logger.debug("Requesting data from fitbit via Url : " + url)
        while True:  # Unlimited Retry attempts
            if request_type == "get" and not headers:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Accept-Language": self.fitbit_language,
                }

            try:
                if request_type == "get":
                    response = requests.get(url, headers=headers, params=params, data=data)
                elif request_type == "post":
                    response = requests.post(url, headers=headers, params=params, data=data)
                else:
                    raise Exception("Invalid request type " + str(request_type))

                if response.status_code == 200:  # Success
                    if url.endswith(".tcx"):  # TCX XML file for GPS data
                        return response
                    return response.json()
                elif response.status_code == 429:  # API Limit reached
                    retry_after = int(response.headers["Fitbit-Rate-Limit-Reset"]) + self.rate_limit_buffer_seconds
                    self.logger.warning(
                        "Fitbit API limit reached. Error code : "
                        + str(response.status_code)
                        + ", Retrying in "
                        + str(retry_after)
                        + " seconds"
                    )
                    print(
                        "Fitbit API limit reached. Error code : "
                        + str(response.status_code)
                        + ", Retrying in "
                        + str(retry_after)
                        + " seconds"
                    )
                    time.sleep(retry_after)
                elif response.status_code == 401:  # Access token expired ( most likely )
                    self.logger.info("Current access token expired; requesting refresh")
                    self.logger.warning(
                        "Error code : " + str(response.status_code) + ", Details : " + response.text
                    )
                    print("Error code : " + str(response.status_code) + ", Details : " + response.text)
                    self.access_token = self.get_new_access_token(self.client_id, self.client_secret)
                    self.logger.info("Access token refresh succeeded")
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    time.sleep(30)
                    if retry_attempts > self.expired_token_max_retry:
                        self.logger.error("Unable to solve the 401 Error. Please debug - " + response.text)
                        raise Exception("Unable to solve the 401 Error. Please debug - " + response.text)
                elif response.status_code in [500, 502, 503, 504]:
                    self.logger.warning("Server Error encountered ( Code 5xx ): Retrying after 120 seconds....")
                    time.sleep(120)
                    if retry_attempts > self.server_error_max_retry:
                        self.logger.error(
                            "Unable to solve the server Error. Retry limit exceed. Please debug - " + response.text
                        )
                        if self.skip_request_on_server_error:
                            self.logger.warning("Retry limit reached for server error : Skipping request -> " + url)
                            return None
                else:
                    self._raise_invalid_grant_if_present(url, response)
                    self.logger.error(
                        "Fitbit API request failed. Status code: " + str(response.status_code) + " " + str(response.text)
                    )
                    print(f"Fitbit API request failed. Status code: {response.status_code}", response.text)
                    response.raise_for_status()
                    return None

            except ConnectionError as err:
                self.logger.error("Retrying in 5 minutes - Failed to connect to internet : " + str(err))
                print("Retrying in 5 minutes - Failed to connect to internet : " + str(err))
            retry_attempts += 1
            time.sleep(30)

    def _raise_invalid_grant_if_present(self, url: str, response) -> None:
        if "/oauth2/token" not in url:
            return

        try:
            response_payload = response.json()
        except ValueError:
            return

        errors = response_payload.get("errors", [])
        for error in errors:
            if error.get("errorType") == "invalid_grant":
                raise InvalidRefreshTokenError(
                    "Fitbit rejected the refresh token (invalid_grant). "
                    "Generate a new refresh token for this app and verify CLIENT_ID/CLIENT_SECRET match it."
                )

    def refresh_fitbit_tokens(self, client_id, client_secret, refresh_token):
        self.logger.info("Attempting to refresh tokens...")
        url = "https://api.fitbit.com/oauth2/token"
        headers = {
            "Authorization": "Basic " + base64.b64encode((client_id + ":" + client_secret).encode()).decode(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        json_data = self.request_data(url, headers=headers, data=data, request_type="post")
        access_token = json_data["access_token"]
        new_refresh_token = json_data["refresh_token"]
        tokens = {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
        }
        with open(self.token_file_path, "w") as file:
            json.dump(tokens, file)
        self.access_token = access_token
        self.logger.info("Fitbit token refresh successful!")
        return access_token, new_refresh_token

    def load_tokens_from_file(self):
        with open(self.token_file_path, "r") as file:
            tokens = json.load(file)
            return tokens.get("access_token"), tokens.get("refresh_token")

    def get_new_access_token(self, client_id, client_secret):
        try:
            access_token, refresh_token = self.load_tokens_from_file()
        except FileNotFoundError:
            refresh_token = input("No token file found. Please enter a valid refresh token : ")
        access_token, _ = self.refresh_fitbit_tokens(client_id, client_secret, refresh_token)
        self.access_token = access_token
        return access_token
