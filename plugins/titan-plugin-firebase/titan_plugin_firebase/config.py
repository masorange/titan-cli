"""Configuration model for the Firebase plugin."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .models import FirebaseEnvironment, FirebaseProjectTarget


class FirebasePluginConfig(BaseModel):
    """Configuration for Firebase plugin access."""

    access_token: Optional[str] = Field(
        None,
        description=(
            "Short-lived Firebase/Google OAuth access token. The Titan plugin "
            "configuration wizard stores this value in keyring, not config.toml."
        ),
        json_schema_extra={
            "format": "password",
            "ui_hidden": True,
        },
    )
    default_project: Optional[str] = Field(
        None,
        description="Default Firebase project ID for single-project operations.",
        json_schema_extra={"config_scope": "project"},
    )
    default_environment: Optional[str] = Field(
        None,
        description="Default environment applied to project targets without one.",
        json_schema_extra={"config_scope": "project"},
    )
    environments: list[FirebaseEnvironment] = Field(
        default_factory=list,
        description="Known logical Firebase environments.",
        json_schema_extra={"config_scope": "project"},
    )
    projects: list[FirebaseProjectTarget] = Field(
        default_factory=list,
        description=(
            "Explicit Firebase project targets to read in multibrand workflows."
        ),
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
    access_token_env_var: str = Field(
        "FIREBASE_ACCESS_TOKEN",
        description=(
            "Environment variable containing a short-lived OAuth access token. "
            "Used before falling back to gcloud ADC."
        ),
        json_schema_extra={"config_scope": "global"},
    )
    oauth_client_id: Optional[str] = Field(
        None,
        description=(
            "Google OAuth desktop client ID used for browser-based Firebase login. "
            "Titan stores this value in keyring when configured interactively."
        ),
        json_schema_extra={"config_scope": "global"},
    )
    oauth_client_secret: Optional[str] = Field(
        None,
        description=(
            "Google OAuth desktop client secret used when Google's token endpoint "
            "requires it for the configured Desktop app client."
        ),
        json_schema_extra={
            "config_scope": "global",
            "format": "password",
        },
    )
    oauth_redirect_port: int = Field(
        0,
        ge=0,
        le=65535,
        description=(
            "Localhost port for Google OAuth callback. Use 0 to let Titan choose "
            "a free port."
        ),
        json_schema_extra={"config_scope": "global"},
    )
    oauth_timeout: int = Field(
        180,
        ge=30,
        description="Seconds to wait for the browser OAuth callback.",
        json_schema_extra={"config_scope": "global"},
    )
    oauth_scopes: list[str] = Field(
        default_factory=lambda: [
            "https://www.googleapis.com/auth/cloud-platform",
        ],
        description=(
            "OAuth scopes Titan will request when a provider-backed Google "
            "OAuth flow is available."
        ),
        json_schema_extra={"config_scope": "global"},
    )
    brand_projects: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Firebase project mapping by brand and environment. Defaults to "
            "environment -> brand -> project_id."
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

    @field_validator("api_base_url")
    @classmethod
    def normalize_api_base_url(cls, value: str) -> str:
        """Normalize the API base URL used by the REST client."""
        stripped = value.strip()
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("api_base_url must start with http:// or https://")
        return stripped.rstrip("/")

    @field_validator("access_token_env_var")
    @classmethod
    def normalize_access_token_env_var(cls, value: str) -> str:
        """Normalize the environment variable name used for OAuth access tokens."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("access_token_env_var is required")
        return stripped

    @field_validator("access_token")
    @classmethod
    def normalize_access_token(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional OAuth access token values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("oauth_scopes", mode="before")
    @classmethod
    def normalize_oauth_scopes(cls, value: Any) -> list[str]:
        """Normalize optional OAuth scope values."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]

    @field_validator("projects", mode="before")
    @classmethod
    def normalize_projects(cls, value: Any) -> Any:
        """Allow project targets to be declared as strings or objects."""
        if value is None:
            return []
        if isinstance(value, (str, dict)):
            value = [value]
        if not isinstance(value, list):
            return value

        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"project_id": item, "brand": item})
            else:
                normalized.append(item)
        return normalized

    @field_validator(
        "oauth_client_id",
        "oauth_client_secret",
        "default_project",
        "default_environment",
    )
    @classmethod
    def normalize_default_project(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional string config values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
