"""Configuration model for the Firebase plugin.

Deliberately small. Two things are NOT here:

- A credential. Authentication is Application Default Credentials, so there is
  nothing for Titan to store, prompt for, or protect.
- Any hardcoded notion of brands, project naming patterns or deployment
  environments. This is a generic plugin: it speaks about Firebase projects,
  configured project sets, optional display labels, generic groups, and
  optional project metadata supplied by each repository.
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
        description=("Firebase project ID used when a workflow does not pass one."),
        json_schema_extra={"config_scope": "project"},
    )
    default_project_set: Optional[str] = Field(
        None,
        description=(
            "Configured project set used by multi-project workflows when no "
            "project_ids param is passed."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    default_environment: Optional[str] = Field(
        None,
        description=(
            "Deployment environment used by project-set workflows when neither "
            "the workflow nor the selected project set names one."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    default_condition_group: Optional[str] = Field(
        None,
        description=(
            "Remote Config condition group used by inventory views when no "
            "workflow param names one."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    condition_groups: dict[str, "FirebaseConditionGroupConfig"] = Field(
        default_factory=dict,
        description=(
            "Named Remote Config condition/value views, for example android or ios."
        ),
        json_schema_extra={"config_scope": "project"},
    )
    project_sets: dict[str, "FirebaseProjectSetConfig"] = Field(
        default_factory=dict,
        description=(
            "Named Firebase project collections for project-scoped workflows."
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

    @field_validator("default_project", "default_project_set", "quota_project_id")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional string config values."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("default_environment")
    @classmethod
    def normalize_default_environment(cls, value: Optional[str]) -> Optional[str]:
        """Normalize the optional default environment."""
        return normalize_environment_name(value)

    @field_validator("default_condition_group")
    @classmethod
    def normalize_default_condition_group(cls, value: Optional[str]) -> Optional[str]:
        """Normalize the optional default condition group name."""
        return normalize_group_name(value)

    @field_validator("condition_groups", mode="before")
    @classmethod
    def normalize_condition_group_keys(cls, value: Any) -> Any:
        """Normalize condition group keys while keeping group payloads intact."""
        if not isinstance(value, dict):
            return value
        normalized: dict[str, Any] = {}
        for key, group in value.items():
            group_name = normalize_group_name(str(key))
            if group_name:
                normalized[group_name] = group
        return normalized

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
        return [
            item.strip() for item in value if isinstance(item, str) and item.strip()
        ]


class FirebaseConditionGroupConfig(BaseModel):
    """A reusable Remote Config condition/value view."""

    label: Optional[str] = Field(None, description="Human-readable group label.")
    include_default: bool = Field(
        True,
        description="Whether the default Remote Config value appears in this view.",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Exact Remote Config condition names included in this view.",
    )
    condition_prefixes: list[str] = Field(
        default_factory=list,
        description="Condition name prefixes included in this view.",
    )
    condition_contains: list[str] = Field(
        default_factory=list,
        description="Case-insensitive fragments matched against condition names.",
    )

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional display labels."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "conditions",
        "condition_prefixes",
        "condition_contains",
        mode="before",
    )
    @classmethod
    def normalize_text_list(cls, value: Any) -> Any:
        """Accept one string or a list of strings, preserving first-seen order."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                if text and text not in items:
                    items.append(text)
        return items


class FirebaseConfiguredProject(BaseModel):
    """One configured Firebase project inside a named project set."""

    project_id: str = Field(..., description="Firebase project ID.")
    label: Optional[str] = Field(None, description="Display label.")
    brand: Optional[str] = Field(
        None,
        description="Optional brand or app-family label for this Firebase project.",
    )
    environment: Optional[str] = Field(
        None,
        description="Optional deployment environment such as dev or pro.",
    )
    groups: list[str] = Field(
        default_factory=list,
        description="Optional group tags used to select subsets of a project set.",
    )

    @field_validator("project_id")
    @classmethod
    def normalize_project_id(cls, value: str) -> str:
        """Normalize and require a Firebase project ID."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("project_id is required")
        return stripped

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional display labels."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("brand")
    @classmethod
    def normalize_brand(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional brand labels."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional environment names."""
        return normalize_environment_name(value)

    @field_validator("groups", mode="before")
    @classmethod
    def normalize_groups(cls, value: Any) -> Any:
        """Accept a single group where a list is expected."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return value
        groups: list[str] = []
        for item in value:
            if isinstance(item, str):
                group = item.strip().casefold()
                if group and group not in groups:
                    groups.append(group)
        return groups


class FirebaseProjectSetConfig(BaseModel):
    """A reusable project-scoped Firebase target set."""

    description: Optional[str] = Field(None, description="Human-readable purpose.")
    default_environment: Optional[str] = Field(
        None,
        description=(
            "Environment selected by default when workflows target this project set."
        ),
    )
    projects: list[FirebaseConfiguredProject] = Field(
        default_factory=list,
        description="Firebase projects in this set, in prompt/display order.",
    )

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional descriptions."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("default_environment")
    @classmethod
    def normalize_default_environment(cls, value: Optional[str]) -> Optional[str]:
        """Normalize the optional project-set default environment."""
        return normalize_environment_name(value)


def normalize_environment_name(value: Optional[str]) -> Optional[str]:
    """Normalize environment names while keeping the vocabulary repo-owned."""
    if value is None:
        return None
    stripped = value.strip().casefold()
    return stripped or None


def normalize_group_name(value: Optional[str]) -> Optional[str]:
    """Normalize configured group names while keeping them repo-owned."""
    if value is None:
        return None
    stripped = value.strip().casefold()
    return stripped or None
