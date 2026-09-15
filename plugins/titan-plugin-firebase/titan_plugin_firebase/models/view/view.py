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
class UIRemoteConfigChange:
    """One pending change to a single parameter value."""

    key: str
    condition: Optional[str]
    value_type: RemoteConfigValueType
    old_raw_value: Optional[str]
    new_raw_value: str
    inherited_from_default: bool = False

    @property
    def target_label(self) -> str:
        """Which value of the parameter this change writes."""
        return self.condition or "valor por defecto"

    @property
    def is_noop(self) -> bool:
        """Whether publishing this change would alter nothing."""
        return self.old_raw_value == self.new_raw_value

    @property
    def creates_conditional_value(self) -> bool:
        """Whether this adds a conditional value the parameter lacked."""
        return self.condition is not None and self.old_raw_value is None

    def describe(self, *, max_value_length: int = 80) -> str:
        """
        One-line summary, published as the Remote Config version description.

        It shows up in the Firebase version history next to the author, which
        is the point: the history should say what changed, not just who
        touched it.
        """

        def _trim(value: Optional[str]) -> str:
            if value is None:
                return "(sin valor)"
            collapsed = " ".join(value.split())
            if len(collapsed) <= max_value_length:
                return collapsed
            return f"{collapsed[: max_value_length - 1]}…"

        return (
            f"Titan: {self.key} [{self.target_label}] "
            f"{_trim(self.old_raw_value)} -> {_trim(self.new_raw_value)}"
        )


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
class UIRemoteConfigPublishResult:
    """Outcome of publishing one template."""

    project_id: str
    validated_only: bool
    etag: Optional[str]
    version: Optional["UIRemoteConfigVersion"]
    change: Optional[UIRemoteConfigChange] = None
    retried_after_conflict: bool = False

    @property
    def version_number(self) -> Optional[str]:
        """Version number Firebase assigned, when it published."""
        return self.version.version_number if self.version else None


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
