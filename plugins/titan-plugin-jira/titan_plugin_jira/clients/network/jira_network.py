"""
Jira Network Layer

Pure HTTP/REST communication with Jira API.
Returns raw JSON responses (dicts).
NO model parsing, NO business logic.
"""

import json
import time
from typing import Dict, List, Union

import requests

from titan_cli.core.logging.config import get_logger

from ...exceptions import JiraAPIError


class JiraNetwork:
    """
    Jira REST API v2 Network Layer.

    Handles HTTP communication with Jira Server/Cloud.
    Returns raw JSON (dicts), does NOT parse to models.
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        timeout: int = 30
    ):
        """
        Initialize Jira network layer.

        Args:
            base_url: Jira instance URL
            email: User email for authentication
            api_token: Jira API token (Personal Access Token)
            timeout: Request timeout in seconds

        Raises:
            JiraAPIError: If required parameters are missing
        """
        # Validate
        if not base_url:
            raise JiraAPIError("JIRA base URL not provided")
        if not api_token:
            raise JiraAPIError("JIRA API token not provided")
        if not email:
            raise JiraAPIError("JIRA user email not provided")

        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token
        self.timeout = timeout
        self._logger = get_logger(__name__)

        # Setup session with auth
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}"
        })

    def make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Union[Dict, List]:
        """
        Make HTTP request to Jira API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (e.g., "issue/PROJ-123")
            **kwargs: Additional arguments for requests (params, json, headers, etc.)

        Returns:
            Raw JSON response as dict or list

        Raises:
            JiraAPIError: If request fails

        Examples:
            >>> network = JiraNetwork(...)
            >>> data = network.make_request("GET", "issue/PROJ-123")
            >>> print(data["key"])
            'PROJ-123'
        """
        # Build full URL (Jira Server uses API v2)
        url = f"{self.base_url}/rest/api/2/{endpoint.lstrip('/')}"

        # Add Content-Type for POST/PUT/PATCH
        if method.upper() in ('POST', 'PUT', 'PATCH') and 'json' in kwargs:
            headers = kwargs.get('headers', {})
            headers['Content-Type'] = 'application/json'
            kwargs['headers'] = headers

        # Log only method + endpoint path — never kwargs/params (may contain JQL, body) or headers (Bearer token)
        start = time.time()

        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )

            # Handle 204 No Content
            if response.status_code == 204:
                self._logger.debug(
                    "jira_request_ok",
                    method=method.upper(),
                    endpoint=endpoint,
                    status_code=204,
                    duration=round(time.time() - start, 3),
                )
                return {}

            response.raise_for_status()

            self._logger.debug(
                "jira_request_ok",
                method=method.upper(),
                endpoint=endpoint,
                status_code=response.status_code,
                duration=round(time.time() - start, 3),
            )

            # Return JSON or empty dict
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
            self._logger.debug(
                "jira_request_failed",
                method=method.upper(),
                endpoint=endpoint,
                status_code=e.response.status_code if e.response is not None else None,
                duration=round(time.time() - start, 3),
            )
            error_msg = f"JIRA API error: {e}"

            # Try to extract error details from response
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg}\nDetails: {json.dumps(error_detail, indent=2)}"
            except (ValueError, AttributeError):
                # If not JSON, show raw text
                error_msg = f"{error_msg}\nResponse: {e.response.text[:500]}"

            # Extract response JSON if available
            try:
                response_json = e.response.json() if e.response.content else None
            except (ValueError, AttributeError):
                response_json = None

            raise JiraAPIError(
                error_msg,
                status_code=e.response.status_code,
                response=response_json
            )

        except requests.exceptions.RequestException as e:
            raise JiraAPIError(f"Request failed: {e}")


__all__ = ["JiraNetwork"]
