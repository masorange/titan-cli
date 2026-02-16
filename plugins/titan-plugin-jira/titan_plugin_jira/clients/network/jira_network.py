"""
Jira Network Layer

Pure HTTP/REST communication with Jira API.
Returns raw JSON responses (dicts).
NO model parsing, NO business logic.
"""

import json
from typing import Dict, List, Union

import requests

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

        try:
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs
            )

            # Handle 204 No Content
            if response.status_code == 204:
                return {}

            response.raise_for_status()

            # Return JSON or empty dict
            return response.json() if response.content else {}

        except requests.exceptions.HTTPError as e:
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
