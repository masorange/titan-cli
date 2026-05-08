"""Pure HTTP/REST communication with PoEditor API."""

import time

import requests

from titan_cli.core.logging.config import get_logger

from ...exceptions import PoEditorAPIError


class PoEditorNetwork:
    """Pure HTTP communication with PoEditor REST API.

    Handles only HTTP requests and responses - no model parsing.
    """

    def __init__(self, api_token: str, timeout: int = 30):
        """Initialize network layer.

        Args:
            api_token: PoEditor API token
            timeout: Request timeout in seconds
        """
        self.base_url = "https://api.poeditor.com/v2"
        self.api_token = api_token
        self.timeout = timeout
        self._logger = get_logger(__name__)

    def make_request(self, endpoint: str, **params) -> dict | list:
        """Make POST request to PoEditor API.

        PoEditor API uses POST for all endpoints (including list/get operations).
        Authentication is via api_token field in POST body.

        Args:
            endpoint: API endpoint (e.g., "projects/list")
            **params: Additional request parameters

        Returns:
            Raw JSON response (result field) as dict or list

        Raises:
            PoEditorAPIError: If request fails or API returns error
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        # PoEditor uses POST with form data for authentication
        data = {"api_token": self.api_token, **params}

        start = time.time()

        try:
            response = requests.post(url, data=data, timeout=self.timeout)

            response.raise_for_status()

            duration = round(time.time() - start, 3)

            self._logger.debug(
                "poeditor_request_ok",
                endpoint=endpoint,
                status_code=response.status_code,
                duration=duration,
            )

            # PoEditor API response format: {"response": {...}, "result": {...}}
            json_response = response.json() if response.content else {}

            # Check API-level status (PoEditor returns 200 even for logical errors)
            api_response = json_response.get("response", {})
            if api_response.get("status") == "fail":
                error_message = api_response.get("message", "Unknown API error")
                error_code = api_response.get("code", "UNKNOWN")
                raise PoEditorAPIError(
                    f"PoEditor API error: {error_message} (code: {error_code})",
                    status_code=response.status_code,
                    response=json_response,
                )

            # Return the result field (actual data)
            return json_response.get("result", {})

        except requests.exceptions.HTTPError as e:
            duration = round(time.time() - start, 3)
            self._logger.error(
                "poeditor_request_failed",
                endpoint=endpoint,
                status_code=e.response.status_code,
                duration=duration,
            )
            raise PoEditorAPIError(
                f"PoEditor API HTTP error: {e}",
                status_code=e.response.status_code,
                response=e.response.json() if e.response.content else None,
            ) from e

        except requests.exceptions.RequestException as e:
            raise PoEditorAPIError(f"Request failed: {e}") from e
