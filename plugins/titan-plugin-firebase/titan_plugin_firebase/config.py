"""Configuration model for the Firebase plugin.

There is deliberately no credential field here. Authentication is Application
Default Credentials, so there is nothing for Titan to store, prompt for, or
protect — see `clients/network/adc_auth.py`.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

DEFAULT_API_BASE_URL = "https://firebaseremoteconfig.googleapis.com/v1"
DEFAULT_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


class FirebasePluginConfig(BaseModel):
    """Configuration for Firebase Remote Config access."""

    default_project: Optional[str] = Field(
        None,
        description="Firebase project ID used when no brand is selected.",
        json_schema_extra={"config_scope": "project"},
    )
    brands: list[str] = Field(
        default_factory=list,
        description=(
            "Brand identifiers this repository publishes to, in display order."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    project_id_pattern: Optional[str] = Field(
        None,
        description=(
            "Pattern building a project ID from a brand, e.g. "
            "'mm-firebase-{brand}'. Placeholders: {brand}, {environment}."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    brand_project_overrides: Dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Brands whose project ID does not follow project_id_pattern, "
            "as brand -> project_id."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    brand_projects: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Explicit project mapping by environment and brand. Shape given by "
            "brand_projects_layout."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    brand_projects_layout: Literal["environment_brand", "brand_environment"] = Field(
        "environment_brand",
        description=(
            "Shape used by brand_projects: environment_brand or brand_environment."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    default_environment: Optional[str] = Field(
        None,
        description="Environment used when brand_projects has more than one.",
        json_schema_extra={"config_scope": "project"},
    )
    quota_project_id: Optional[str] = Field(
        None,
        description=(
            "Project billed for API quota (x-goog-user-project). Defaults to "
            "the project being read, which is normally what you want."
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

    @field_validator(
        "default_project",
        "default_environment",
        "project_id_pattern",
        "quota_project_id",
    )
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional string config values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("brands", "oauth_scopes", mode="before")
    @classmethod
    def normalize_string_list(cls, value: Any) -> Any:
        """Accept a single string where a list is expected."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
