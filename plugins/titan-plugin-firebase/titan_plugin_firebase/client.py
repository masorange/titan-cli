"""Firebase client for ADC-backed Remote Config REST operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import requests

from . import auth
from .config import FirebasePluginConfig
from .exceptions import FirebaseClientError


@dataclass(frozen=True)
class RemoteConfigTemplate:
    """Remote Config template returned by Firebase."""

    project_id: str
    template: dict[str, Any]
    etag: Optional[str]

    @property
    def version(self) -> Any:
        """Return the Remote Config template version payload, when present."""
        return self.template.get("version")


class FirebaseClient:
    """Client facade for Firebase Remote Config operations."""

    def __init__(self, config: FirebasePluginConfig):
        """Initialize the Firebase client with validated plugin config."""
        self.config = config

    def is_gcloud_installed(self) -> bool:
        """Return whether the gcloud CLI is installed."""
        return auth.is_gcloud_installed()

    def get_active_account(self) -> Optional[str]:
        """Return the active gcloud account, if one is configured."""
        return auth.get_active_account()

    def get_adc_access_token(self) -> Optional[str]:
        """Return the current ADC bearer token, if available."""
        return auth.get_adc_access_token()

    def get_login_command(self) -> str:
        """Return the command users should run to create an ADC session."""
        return auth.adc_login_hint()

    def is_available(self) -> bool:
        """Return whether gcloud and ADC are available for Firebase requests."""
        return self.is_gcloud_installed() and bool(self.get_adc_access_token())

    def get_remote_config(self, project_id: str) -> RemoteConfigTemplate:
        """
        Read a Firebase Remote Config template for one project.

        Args:
            project_id: Firebase project ID.

        Returns:
            RemoteConfigTemplate containing the JSON template and ETag.

        Raises:
            FirebaseClientError: If ADC is missing or the API request fails.
        """
        normalized_project_id = project_id.strip() if project_id else ""
        if not normalized_project_id:
            raise FirebaseClientError("Firebase project_id is required.")

        token = self.get_adc_access_token()
        if not token:
            raise FirebaseClientError(
                "Firebase ADC token not available. Run: "
                f"{self.get_login_command()}"
            )

        url = (
            f"{self.config.api_base_url}/projects/"
            f"{normalized_project_id}/remoteConfig"
        )
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.config.request_timeout,
            )
        except requests.RequestException as exc:
            raise FirebaseClientError(
                f"Firebase Remote Config request failed: {exc}"
            ) from exc

        if response.status_code == 200:
            try:
                template = response.json()
            except ValueError as exc:
                raise FirebaseClientError(
                    "Firebase Remote Config response was not valid JSON."
                ) from exc

            return RemoteConfigTemplate(
                project_id=normalized_project_id,
                template=template,
                etag=response.headers.get("ETag"),
            )

        detail = self._extract_error_detail(response)
        if response.status_code == 401:
            raise FirebaseClientError(
                "Firebase ADC token was rejected or expired. Run: "
                f"{self.get_login_command()}. {detail}"
            )
        if response.status_code == 403:
            raise FirebaseClientError(
                "Firebase Remote Config permission denied for project "
                f"'{normalized_project_id}'. {detail}"
            )
        if response.status_code == 404:
            raise FirebaseClientError(
                "Firebase Remote Config project or template not found for "
                f"'{normalized_project_id}'. {detail}"
            )

        raise FirebaseClientError(
            "Firebase Remote Config request failed with status "
            f"{response.status_code}. {detail}"
        )

    def _extract_error_detail(self, response: requests.Response) -> str:
        """Extract a concise error detail from a Firebase HTTP response."""
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if message:
                    return str(message)
            if error:
                return str(error)

        text = (response.text or "").strip()
        return text or "No response detail provided."
