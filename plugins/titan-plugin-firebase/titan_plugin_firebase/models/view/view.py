"""UI models: pre-formatted for rendering, never used for network payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..values import RemoteConfigValueType


@dataclass(frozen=True)
class UIAdcIdentity:
    """Who Application Default Credentials resolved to."""

    account: Optional[str]
    credential_kind: str
    quota_project_id: Optional[str]
    scopes: tuple[str, ...] = ()

    @property
    def is_user_credential(self) -> bool:
        """Whether publishes will be attributed to a real person."""
        return self.credential_kind == "user"

    @property
    def display_account(self) -> str:
        """Account label for the UI."""
        return self.account or "(cuenta no identificada)"


@dataclass(frozen=True)
class UIRemoteConfigValue:
    """One Remote Config value, parsed and ready to display."""

    raw_value: Optional[str]
    parsed_value: Any
    value_type: RemoteConfigValueType
    use_in_app_default: bool
    display_value: str


@dataclass(frozen=True)
class UIRemoteConfigCondition:
    """One Remote Config condition — the environment-like axis of a template."""

    name: str
    expression: Optional[str]
    tag_color: Optional[str]

    @property
    def display_expression(self) -> str:
        """Expression collapsed to a single line for tables."""
        if not self.expression:
            return "—"
        return " ".join(self.expression.split())


@dataclass(frozen=True)
class UIRemoteConfigParameter:
    """One Remote Config parameter with its values resolved per target."""

    key: str
    description: Optional[str]
    value_type: RemoteConfigValueType
    declared_value_type: RemoteConfigValueType
    default_value: Optional[UIRemoteConfigValue]
    conditional_values: dict[str, UIRemoteConfigValue] = field(default_factory=dict)

    @property
    def conditional_names(self) -> list[str]:
        """Condition names this parameter overrides, sorted."""
        return sorted(self.conditional_values)

    def value_for(self, condition_name: Optional[str]) -> Optional[UIRemoteConfigValue]:
        """Return the value for one condition, or the default when None."""
        if condition_name is None:
            return self.default_value
        return self.conditional_values.get(condition_name)


@dataclass(frozen=True)
class UIRemoteConfigVersion:
    """Version metadata of a published template."""

    version_number: Optional[str]
    update_time: Optional[str]
    update_user_email: Optional[str]
    update_origin: Optional[str]
    update_type: Optional[str]
    description: Optional[str]

    @property
    def display_author(self) -> str:
        """Author label for the UI."""
        return self.update_user_email or "(autor desconocido)"


@dataclass(frozen=True)
class UIRemoteConfigTemplate:
    """A Remote Config template ready to render."""

    project_id: str
    etag: Optional[str]
    parameters: list[UIRemoteConfigParameter]
    conditions: list[UIRemoteConfigCondition]
    version: Optional[UIRemoteConfigVersion]
    parameter_group_names: list[str] = field(default_factory=list)

    @property
    def parameter_count(self) -> int:
        """Number of parameters in the template."""
        return len(self.parameters)

    def parameter(self, key: str) -> Optional[UIRemoteConfigParameter]:
        """Return one parameter by key."""
        for parameter in self.parameters:
            if parameter.key == key:
                return parameter
        return None
