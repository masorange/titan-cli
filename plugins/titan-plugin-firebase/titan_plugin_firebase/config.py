"""Configuration model for the Firebase plugin.

Deliberately small. Two things are NOT here:

- A credential. Authentication is Application Default Credentials, so there is
  nothing for Titan to store, prompt for, or protect.
- Any notion of a brand, a project naming pattern, or an environment map. This
  is a generic plugin: it speaks about Firebase projects, and a project ID is
  either configured as the default or passed in by whoever knows how to
  produce it. A repository that runs one Firebase project per brand keeps that
  mapping in its own plugin — it is that repository's vocabulary, not
  Firebase's — and feeds `firebase_project_ids` to the multi-project steps.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

DEFAULT_API_BASE_URL = "https://firebaseremoteconfig.googleapis.com/v1"
DEFAULT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class FirebasePluginConfig(BaseModel):
    """Configuration for Firebase Remote Config access."""

    default_project: Optional[str] = Field(
        None,
        description=(
            "Firebase project ID used when a workflow does not pass one."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    quota_project_id: Optional[str] = Field(
        None,
        description=(
            "Project billed for API quota. Defaults to the credential's own "
            "quota project, or the project being read. Override it when your "
            "account lacks serviceusage.services.use on that project."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    api_base_url: str = Field(
        DEFAULT_API_BASE_URL,
        description="Firebase Remote Config REST API base URL.",
        json_schema_extra={"config_scope": "global"},
    )
    request_timeout: int = Field(
        30,
        ge=1,
        description="HTTP request timeout in seconds.",
        json_schema_extra={"config_scope": "global"},
    )
    oauth_scopes: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SCOPES),
        description=(
            "Scopes requested from Application Default Credentials. "
            "cloud-platform covers Remote Config; the narrow scope is "
            "https://www.googleapis.com/auth/firebase.remoteconfig."
        ),
        json_schema_extra={"config_scope": "global"},
    )

    @field_validator("api_base_url")
    @classmethod
    def normalize_api_base_url(cls, value: str) -> str:
        """Normalize the API base URL used by the REST client."""
        stripped = value.strip()
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("api_base_url must start with http:// or https://")
        return stripped.rstrip("/")

    @field_validator("default_project", "quota_project_id")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional string config values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("oauth_scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, value: Any) -> Any:
        """Accept a single scope where a list is expected."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
