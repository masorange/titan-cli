"""Configuration model for the Firebase plugin."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class FirebasePluginConfig(BaseModel):
    """Configuration for Firebase plugin access."""

    default_project: Optional[str] = Field(
        None,
        description="Default Firebase project ID for single-project operations.",
        json_schema_extra={"config_scope": "project"},
    )
    api_base_url: str = Field(
        "https://firebaseremoteconfig.googleapis.com/v1",
        description="Firebase Remote Config REST API base URL.",
        json_schema_extra={"config_scope": "global"},
    )
    request_timeout: int = Field(
        30,
        ge=1,
        description="HTTP request timeout in seconds.",
        json_schema_extra={"config_scope": "global"},
    )
    brand_projects: Dict[str, Any] = Field(
        default_factory=dict,
        description="Reserved for PR2 multibrand project resolution.",
        json_schema_extra={"config_scope": "project"},
    )

    @field_validator("api_base_url")
    @classmethod
    def normalize_api_base_url(cls, value: str) -> str:
        """Normalize the API base URL used by the REST client."""
        stripped = value.strip()
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("api_base_url must start with http:// or https://")
        return stripped.rstrip("/")

    @field_validator("default_project")
    @classmethod
    def normalize_default_project(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional default project values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
