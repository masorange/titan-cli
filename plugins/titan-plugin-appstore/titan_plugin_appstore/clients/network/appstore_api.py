"""
Low-level HTTP client for App Store Connect API.

Handles JWT authentication, token caching, and raw HTTP requests.
"""

import jwt
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ...exceptions import AuthenticationError, APIError


class AppStoreConnectAPI:
    """
    HTTP client for App Store Connect API.

    Responsibilities:
    - JWT token generation and caching
    - HTTP request execution
    - Error handling and response parsing
    """

    API_HOST = "api.appstoreconnect.apple.com"
    API_VERSION = "v1"
    JWT_ALGORITHM = "ES256"
    TOKEN_EXPIRY_MINUTES = 20

    def __init__(
        self,
        key_id: str,
        issuer_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        private_key_content: Optional[str] = None,
    ):
        """
        Initialize API client.

        Args:
            key_id: Key ID from App Store Connect
            issuer_id: Issuer ID (None for Individual Keys)
            private_key_path: Path to .p8 private key file
            private_key_content: Content of .p8 private key

        Raises:
            AuthenticationError: If credentials are invalid
        """
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.is_individual_key = not issuer_id or issuer_id.strip() == ""

        # Load private key
        if private_key_path:
            try:
                with open(private_key_path, "r") as f:
                    self.private_key = f.read()
            except Exception as e:
                raise AuthenticationError(f"Failed to load private key: {e}")
        elif private_key_content:
            self.private_key = private_key_content
        else:
            raise AuthenticationError(
                "Either private_key_path or private_key_content must be provided"
            )

        self._token_cache: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    def _generate_token(self) -> str:
        """Generate JWT token for API authentication."""
        now = int(time.time())
        exp = now + (self.TOKEN_EXPIRY_MINUTES * 60)

        headers = {"alg": self.JWT_ALGORITHM, "kid": self.key_id, "typ": "JWT"}

        # Individual Keys use "sub": "user", Team Keys use "iss": issuer_id
        if self.is_individual_key:
            payload = {"sub": "user", "iat": now, "exp": exp, "aud": "appstoreconnect-v1"}
        else:
            payload = {
                "iss": self.issuer_id,
                "iat": now,
                "exp": exp,
                "aud": "appstoreconnect-v1",
            }

        try:
            token = jwt.encode(payload, self.private_key, algorithm=self.JWT_ALGORITHM, headers=headers)
            return token
        except Exception as e:
            raise AuthenticationError(f"Failed to generate JWT token: {e}")

    def _get_token(self) -> str:
        """Get valid JWT token, using cache if available."""
        now = datetime.now()

        # Check if cached token is still valid
        if self._token_cache and self._token_expiry and now < self._token_expiry:
            return self._token_cache

        # Generate new token
        self._token_cache = self._generate_token()
        self._token_expiry = now + timedelta(minutes=self.TOKEN_EXPIRY_MINUTES - 1)

        return self._token_cache

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authorization."""
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _build_url(self, path: str, query_params: Optional[Dict[str, Any]] = None) -> str:
        """Build full API URL."""
        url = f"https://{self.API_HOST}/{self.API_VERSION}{path}"
        if query_params:
            from urllib.parse import urlencode

            url += f"?{urlencode(query_params)}"
        return url

    def request(
        self,
        method: str,
        path: str,
        query_params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            path: API endpoint path
            query_params: URL query parameters
            json_data: JSON request body

        Returns:
            API response as dict

        Raises:
            APIError: If request fails
        """
        url = self._build_url(path, query_params)
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method, url=url, headers=headers, json=json_data, timeout=30
            )
        except requests.Timeout:
            raise APIError("Request timed out")
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")

        # Handle error responses
        if not response.ok:
            error_data = None
            try:
                error_data = response.json()
            except:
                pass

            error_msg = f"API request failed with status {response.status_code}"
            if error_data and "errors" in error_data:
                errors = error_data["errors"]
                if errors:
                    error_msg = errors[0].get("detail", error_msg)

            raise APIError(error_msg, status_code=response.status_code, response_data=error_data)

        # Return JSON if present, otherwise empty dict
        if response.content:
            try:
                return response.json()
            except:
                return {}
        return {}

    def get(self, path: str, query_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request shorthand."""
        return self.request("GET", path, query_params=query_params)

    def post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """POST request shorthand."""
        return self.request("POST", path, json_data=json_data)

    def patch(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH request shorthand."""
        return self.request("PATCH", path, json_data=json_data)

    def delete(self, path: str) -> None:
        """DELETE request shorthand."""
        self.request("DELETE", path)
