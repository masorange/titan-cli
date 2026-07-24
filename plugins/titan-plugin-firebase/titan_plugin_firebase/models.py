"""Domain models for Firebase Remote Config inventory."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RemoteConfigValueType(str, Enum):
    """Supported Firebase Remote Config parameter value types."""

    BOOLEAN = "BOOLEAN"
    JSON = "JSON"
    NUMBER = "NUMBER"
    STRING = "STRING"
    UNKNOWN = "UNKNOWN"


class FirebaseEnvironment(BaseModel):
    """A logical Firebase environment such as dev, pre, staging, or prod."""

    name: str = Field(..., description="Stable environment identifier.")
    display_name: Optional[str] = Field(
        None,
        description="Human-friendly environment label.",
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternate names accepted for this environment.",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Normalize environment identifiers."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("environment name is required")
        return stripped


class FirebaseProjectTarget(BaseModel):
    """A Firebase project resolved for one brand/environment target."""

    project_id: str = Field(..., description="Firebase project ID.")
    brand: Optional[str] = Field(None, description="Brand owning the project.")
    environment: Optional[str] = Field(
        None,
        description="Logical environment for the project.",
    )
    platform: Optional[str] = Field(None, description="Optional app platform.")
    label: Optional[str] = Field(None, description="Optional display label.")

    @field_validator("project_id")
    @classmethod
    def normalize_project_id(cls, value: str) -> str:
        """Normalize Firebase project IDs."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("project_id is required")
        return stripped

    @field_validator("brand", "environment", "platform", "label")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        """Normalize optional target fields."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def default_brand_and_label(self) -> FirebaseProjectTarget:
        """Default missing display metadata from the project ID."""
        if self.brand is None:
            self.brand = self.project_id
        if self.label is None:
            parts = [self.environment, self.brand, self.platform]
            self.label = "/".join(part for part in parts if part) or self.project_id
        return self

    def reference(self) -> str:
        """Return a stable user-facing target reference."""
        if self.label:
            return f"{self.label} ({self.project_id})"
        return self.project_id


class RemoteConfigParameterValue(BaseModel):
    """Raw Remote Config parameter value payload."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    value: Optional[str] = Field(None, description="Raw string value.")
    use_in_app_default: bool = Field(
        False,
        alias="useInAppDefault",
        description="Whether apps should use their in-app default.",
    )


class RemoteConfigParameter(BaseModel):
    """Raw Remote Config parameter payload."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    description: Optional[str] = Field(None, description="Parameter description.")
    default_value: Optional[RemoteConfigParameterValue] = Field(
        None,
        alias="defaultValue",
        description="Default value payload.",
    )
    conditional_values: dict[str, RemoteConfigParameterValue] = Field(
        default_factory=dict,
        alias="conditionalValues",
        description="Conditional values keyed by Firebase condition name.",
    )
    value_type: RemoteConfigValueType = Field(
        RemoteConfigValueType.UNKNOWN,
        alias="valueType",
        description="Remote Config declared value type, when present.",
    )

    @field_validator("value_type", mode="before")
    @classmethod
    def normalize_value_type(cls, value: Any) -> RemoteConfigValueType:
        """Normalize unknown or absent Firebase value type names."""
        return normalize_remote_config_value_type(value)

    def raw_values(self) -> list[Optional[str]]:
        """Return all raw values declared for this parameter."""
        values: list[Optional[str]] = []
        if self.default_value:
            values.append(self.default_value.value)
        values.extend(value.value for value in self.conditional_values.values())
        return values


class RemoteConfigTypedValue(BaseModel):
    """A Remote Config value with inferred type and parsed representation."""

    raw_value: Optional[str] = Field(None, description="Raw Remote Config value.")
    parsed_value: Any = Field(None, description="Parsed value when supported.")
    value_type: RemoteConfigValueType = Field(
        RemoteConfigValueType.UNKNOWN,
        description="Effective value type for this value.",
    )
    use_in_app_default: bool = Field(
        False,
        description="Whether apps should use their in-app default.",
    )


class RemoteConfigParameterInventory(BaseModel):
    """Normalized inventory for one Remote Config parameter."""

    key: str
    description: Optional[str] = None
    declared_value_type: RemoteConfigValueType = RemoteConfigValueType.UNKNOWN
    inferred_value_type: RemoteConfigValueType = RemoteConfigValueType.UNKNOWN
    value_type: RemoteConfigValueType = RemoteConfigValueType.UNKNOWN
    default_value: Optional[RemoteConfigTypedValue] = None
    conditional_values: dict[str, RemoteConfigTypedValue] = Field(default_factory=dict)
    conditional_value_names: list[str] = Field(default_factory=list)


class RemoteConfigKeyOccurrence(BaseModel):
    """One key occurrence inside one Firebase project."""

    key: str
    project_id: str
    brand: Optional[str] = None
    environment: Optional[str] = None
    platform: Optional[str] = None
    target_label: Optional[str] = None
    value_type: RemoteConfigValueType
    declared_value_type: RemoteConfigValueType
    inferred_value_type: RemoteConfigValueType
    default_value: Optional[RemoteConfigTypedValue] = None
    conditional_value_names: list[str] = Field(default_factory=list)
    description: Optional[str] = None


class RemoteConfigKeyInventory(BaseModel):
    """Aggregated inventory for one key across Firebase projects."""

    key: str
    occurrences: list[RemoteConfigKeyOccurrence] = Field(default_factory=list)
    projects_present: list[str] = Field(default_factory=list)
    projects_missing: list[str] = Field(default_factory=list)
    observed_types: list[RemoteConfigValueType] = Field(default_factory=list)
    has_type_mismatch: bool = False


class RemoteConfigProjectInventory(BaseModel):
    """Remote Config inventory for one Firebase project target."""

    target: FirebaseProjectTarget
    etag: Optional[str] = None
    version: Optional[dict[str, Any]] = None
    version_number: Optional[str] = None
    parameter_count: int = 0
    parameters: dict[str, RemoteConfigParameterInventory] = Field(
        default_factory=dict
    )


class RemoteConfigInventoryFailure(BaseModel):
    """Failure collected while reading one Firebase project target."""

    target: FirebaseProjectTarget
    message: str


class RemoteConfigInventory(BaseModel):
    """Aggregated Remote Config inventory across Firebase project targets."""

    targets: list[FirebaseProjectTarget] = Field(default_factory=list)
    projects: list[RemoteConfigProjectInventory] = Field(default_factory=list)
    keys: list[RemoteConfigKeyInventory] = Field(default_factory=list)
    failures: list[RemoteConfigInventoryFailure] = Field(default_factory=list)

    @property
    def project_count(self) -> int:
        """Return the number of projects read successfully."""
        return len(self.projects)

    @property
    def key_count(self) -> int:
        """Return the number of unique keys found."""
        return len(self.keys)


def normalize_remote_config_value_type(value: Any) -> RemoteConfigValueType:
    """Normalize a Firebase value type into the local enum."""
    if isinstance(value, RemoteConfigValueType):
        return value
    if value is None:
        return RemoteConfigValueType.UNKNOWN

    normalized = str(value).strip().upper()
    if not normalized:
        return RemoteConfigValueType.UNKNOWN

    return RemoteConfigValueType.__members__.get(
        normalized,
        RemoteConfigValueType.UNKNOWN,
    )


def infer_remote_config_value_type(value: Optional[str]) -> RemoteConfigValueType:
    """Infer the Remote Config value type from a raw string."""
    if value is None:
        return RemoteConfigValueType.UNKNOWN

    stripped = value.strip()
    if not stripped:
        return RemoteConfigValueType.STRING

    lowered = stripped.lower()
    if lowered in {"true", "false"}:
        return RemoteConfigValueType.BOOLEAN

    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
        except ValueError:
            return RemoteConfigValueType.STRING
        if isinstance(parsed, (dict, list)):
            return RemoteConfigValueType.JSON

    try:
        float(stripped)
    except ValueError:
        return RemoteConfigValueType.STRING

    return RemoteConfigValueType.NUMBER


def parse_remote_config_value(
    value: Optional[str],
    value_type: RemoteConfigValueType,
) -> Any:
    """Parse a raw Remote Config value according to its effective type."""
    if value is None:
        return None

    stripped = value.strip()
    if value_type == RemoteConfigValueType.BOOLEAN:
        lowered = stripped.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return value

    if value_type == RemoteConfigValueType.JSON:
        try:
            return json.loads(stripped)
        except ValueError:
            return value

    if value_type == RemoteConfigValueType.NUMBER:
        try:
            parsed = float(stripped)
        except ValueError:
            return value
        if parsed.is_integer() and "." not in stripped and "e" not in stripped.lower():
            return int(parsed)
        return parsed

    return value


def build_parameter_inventory(
    key: str,
    payload: dict[str, Any],
) -> RemoteConfigParameterInventory:
    """Build a normalized parameter inventory item from a raw template payload."""
    parameter = RemoteConfigParameter.model_validate(payload)
    inferred_types = [
        inferred
        for raw_value in parameter.raw_values()
        if (inferred := infer_remote_config_value_type(raw_value))
        != RemoteConfigValueType.UNKNOWN
    ]
    inferred_value_type = (
        inferred_types[0] if inferred_types else RemoteConfigValueType.UNKNOWN
    )
    value_type = (
        parameter.value_type
        if parameter.value_type != RemoteConfigValueType.UNKNOWN
        else inferred_value_type
    )

    def _typed_value(
        raw_value: RemoteConfigParameterValue,
    ) -> RemoteConfigTypedValue:
        return RemoteConfigTypedValue(
            raw_value=raw_value.value,
            parsed_value=parse_remote_config_value(raw_value.value, value_type),
            value_type=value_type,
            use_in_app_default=raw_value.use_in_app_default,
        )

    return RemoteConfigParameterInventory(
        key=key,
        description=parameter.description,
        declared_value_type=parameter.value_type,
        inferred_value_type=inferred_value_type,
        value_type=value_type,
        default_value=(
            _typed_value(parameter.default_value)
            if parameter.default_value is not None
            else None
        ),
        conditional_values={
            condition_name: _typed_value(raw_value)
            for condition_name, raw_value in parameter.conditional_values.items()
        },
        conditional_value_names=sorted(parameter.conditional_values),
    )
