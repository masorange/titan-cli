"""
Network models for the Remote Config REST template.

These stay faithful to the API payload: camelCase aliases, `extra="allow"`
so fields Titan does not model yet survive a read-modify-write, and no
presentation logic.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ...values import RemoteConfigValueSource


class NetworkParameterValue(BaseModel):
    """One Remote Config value payload (`defaultValue` or a conditional one)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    value: Optional[str] = Field(None, description="Raw string value.")
    use_in_app_default: Optional[bool] = Field(
        None,
        alias="useInAppDefault",
        description="Whether clients should fall back to their in-app default.",
    )
    personalization_value: Optional[Any] = Field(
        None,
        alias="personalizationValue",
        description="Remote Config personalization-managed value.",
    )
    experiment_value: Optional[Any] = Field(
        None,
        alias="experimentValue",
        description="A/B Testing experiment-managed value.",
    )
    rollout_value: Optional[Any] = Field(
        None,
        alias="rolloutValue",
        description="Remote Config rollout-managed value.",
    )

    @property
    def value_source(self) -> RemoteConfigValueSource:
        """Return the Firebase union field that owns this value."""
        blocked_sources = [
            source for source in self.value_sources if not source.is_titan_editable
        ]
        if blocked_sources:
            return blocked_sources[0]
        if RemoteConfigValueSource.LITERAL in self.value_sources:
            return RemoteConfigValueSource.LITERAL
        if RemoteConfigValueSource.IN_APP_DEFAULT in self.value_sources:
            return RemoteConfigValueSource.IN_APP_DEFAULT
        return RemoteConfigValueSource.UNKNOWN

    @property
    def value_sources(self) -> tuple[RemoteConfigValueSource, ...]:
        """Return every known union field present in this payload."""
        sources: list[RemoteConfigValueSource] = []
        if self.value is not None:
            sources.append(RemoteConfigValueSource.LITERAL)
        if self.use_in_app_default is True:
            sources.append(RemoteConfigValueSource.IN_APP_DEFAULT)
        if self.personalization_value is not None:
            sources.append(RemoteConfigValueSource.PERSONALIZATION)
        if self.experiment_value is not None:
            sources.append(RemoteConfigValueSource.EXPERIMENT)
        if self.rollout_value is not None:
            sources.append(RemoteConfigValueSource.ROLLOUT)
        if self.model_extra:
            sources.append(RemoteConfigValueSource.UNKNOWN)
        if not sources:
            sources.append(RemoteConfigValueSource.UNKNOWN)
        return tuple(sources)


class NetworkParameter(BaseModel):
    """One Remote Config parameter payload."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    description: Optional[str] = Field(None, description="Developer-facing note.")
    default_value: Optional[NetworkParameterValue] = Field(
        None,
        alias="defaultValue",
        description="Value used when no condition matches.",
    )
    conditional_values: dict[str, NetworkParameterValue] = Field(
        default_factory=dict,
        alias="conditionalValues",
        description="Values keyed by Remote Config condition name.",
    )
    value_type: Optional[str] = Field(
        None,
        alias="valueType",
        description="Declared value type, when the parameter has one.",
    )

    def raw_values(self) -> list[Optional[str]]:
        """Return every raw value declared by this parameter."""
        values: list[Optional[str]] = []
        if self.default_value:
            values.append(self.default_value.value)
        values.extend(value.value for value in self.conditional_values.values())
        return values


class NetworkCondition(BaseModel):
    """One Remote Config condition — what Firebase uses to model environments."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str = Field(..., description="Condition name referenced by parameters.")
    expression: Optional[str] = Field(None, description="Condition expression.")
    tag_color: Optional[str] = Field(
        None,
        alias="tagColor",
        description="Colour the Firebase console shows for this condition.",
    )


class NetworkVersionUser(BaseModel):
    """The identity Firebase recorded for a template version."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    email: Optional[str] = Field(None, description="Author email.")
    name: Optional[str] = Field(None, description="Author display name.")
    image_url: Optional[str] = Field(None, alias="imageUrl")


class NetworkVersion(BaseModel):
    """Version metadata Firebase attaches to every published template."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    version_number: Optional[str] = Field(None, alias="versionNumber")
    update_time: Optional[str] = Field(None, alias="updateTime")
    update_user: Optional[NetworkVersionUser] = Field(None, alias="updateUser")
    update_origin: Optional[str] = Field(None, alias="updateOrigin")
    update_type: Optional[str] = Field(None, alias="updateType")
    description: Optional[str] = Field(None, description="Publish description.")


class NetworkRemoteConfigTemplate(BaseModel):
    """
    A whole Remote Config template.

    Remote Config has no per-key write API: publishing replaces the entire
    template, so anything dropped here would be deleted from the project.
    `extra="allow"` plus dumping by alias with `exclude_none` is what keeps an
    unmodelled field alive through a read-modify-write.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    conditions: list[NetworkCondition] = Field(default_factory=list)
    parameters: dict[str, NetworkParameter] = Field(default_factory=dict)
    parameter_groups: dict[str, Any] = Field(
        default_factory=dict,
        alias="parameterGroups",
    )
    version: Optional[NetworkVersion] = Field(None)

    def to_payload(self) -> dict[str, Any]:
        """Serialize back to the exact JSON shape the REST API expects."""
        return self.model_dump(by_alias=True, exclude_none=True)
