"""UI models: pre-formatted for rendering, never used for network payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..targets import FirebaseProjectTarget
from ..values import (
    RemoteConfigValueSource,
    RemoteConfigValueType,
    normalize_value_source,
    normalize_value_type,
)


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
class UIFirebaseProject:
    """One Firebase project available to the active Google credentials."""

    project_id: str
    display_name: Optional[str]
    name: Optional[str]
    project_number: Optional[str]
    configured_label: Optional[str] = None
    brand: Optional[str] = None
    environment: Optional[str] = None
    groups: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        """Human-friendly display name."""
        return self.configured_label or self.display_name or self.project_id

    @property
    def description(self) -> str:
        """Compact secondary text for option lists."""
        parts = []
        if self.configured_label and self.display_name:
            parts.append(self.display_name)
        if self.environment:
            parts.append(self.environment.upper())
        if self.brand:
            parts.append(self.brand)
        if self.groups:
            parts.append(", ".join(self.groups))
        if self.display_name and self.display_name != self.project_id:
            parts.append(self.display_name)
        if self.project_number:
            parts.append(f"#{self.project_number}")
        return " · ".join(dict.fromkeys(parts))


@dataclass(frozen=True)
class UIRemoteConfigValue:
    """One Remote Config value, parsed and ready to display."""

    raw_value: Optional[str]
    parsed_value: Any
    value_type: RemoteConfigValueType
    use_in_app_default: bool
    display_value: str
    source: RemoteConfigValueSource = RemoteConfigValueSource.LITERAL

    def __post_init__(self) -> None:
        """Normalize value type/source strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))
        object.__setattr__(self, "source", normalize_value_source(self.source))

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

    @property
    def source_label(self) -> str:
        """Short user-facing value-source label."""
        return self.source.display_label

    @property
    def is_titan_editable(self) -> bool:
        """Whether Titan can replace this value through the current workflows."""
        return self.source.is_titan_editable

    @property
    def is_firebase_managed(self) -> bool:
        """Whether Firebase owns this value via personalization, experiment or rollout."""
        return self.source.is_firebase_managed


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

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))
        object.__setattr__(
            self,
            "declared_value_type",
            normalize_value_type(self.declared_value_type),
        )

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

    @property
    def conditional_names(self) -> list[str]:
        """Condition names this parameter overrides, sorted."""
        return sorted(self.conditional_values)

    @property
    def default_display_value(self) -> str:
        """Default value rendered for compact tables."""
        return self.default_value.display_value if self.default_value else "—"

    @property
    def conditional_values_summary(self) -> str:
        """All condition-specific values rendered in deterministic order."""
        if not self.conditional_values:
            return "—"
        return " | ".join(
            f"{name}={self.conditional_values[name].display_value}"
            for name in sorted(self.conditional_values)
        )

    @property
    def value_summary(self) -> str:
        """Default and condition values in one readable line."""
        return (
            f"default={self.default_display_value}; "
            f"conditions={self.conditional_values_summary}"
        )

    @property
    def value_sources(self) -> list[RemoteConfigValueSource]:
        """Value sources present in default and conditional entries."""
        sources = [
            value.source
            for value in [self.default_value, *self.conditional_values.values()]
            if value is not None
        ]
        return sorted(set(sources), key=lambda source: source.value)

    @property
    def has_unsupported_value_source(self) -> bool:
        """Whether any value cannot be edited by Titan's literal write path."""
        return any(not source.is_titan_editable for source in self.value_sources)

    @property
    def source_summary(self) -> str:
        """All value sources in deterministic order."""
        if not self.value_sources:
            return "—"
        return " / ".join(source.display_label for source in self.value_sources)

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

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

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
class UIRemoteConfigKeyCopyPlanEntry:
    """One missing key to create in one target project."""

    key: str
    source: FirebaseProjectTarget
    target: FirebaseProjectTarget
    value_type: RemoteConfigValueType

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))

    @property
    def detail(self) -> str:
        """One-line explanation for the copy plan table."""
        return (
            f"crear {self.key} ({self.value_type.display_label}) "
            f"desde {self.source.reference()}"
        )


@dataclass(frozen=True)
class UIRemoteConfigKeyCopyResult:
    """Outcome of validating or publishing one copied Remote Config key."""

    source_project_id: str
    project_id: str
    key: str
    value_type: RemoteConfigValueType
    validated_only: bool
    etag: Optional[str]
    version: Optional["UIRemoteConfigVersion"]
    retried_after_conflict: bool = False

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

    @property
    def version_number(self) -> Optional[str]:
        """Version number Firebase assigned, when it published."""
        return self.version.version_number if self.version else None


@dataclass(frozen=True)
class UIRemoteConfigKeyCopyOutcome:
    """What happened when one copied key was validated or published."""

    entry: UIRemoteConfigKeyCopyPlanEntry
    published: Optional[UIRemoteConfigKeyCopyResult] = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """Whether Firebase accepted the copy."""
        return self.error is None and self.published is not None

    @property
    def detail(self) -> str:
        """One-line result for the report table."""
        if self.error is not None:
            return self.error
        if self.published is None:
            return "sin publicar"
        if self.published.validated_only:
            return "validado"
        version = self.published.version_number or "?"
        if self.published.retried_after_conflict:
            return f"versión {version} (reintentada por ETag)"
        return f"versión {version}"


@dataclass(frozen=True)
class UIRemoteConfigKeyCreateRequest:
    """Typed request to create one Remote Config parameter."""

    key: str
    value_type: RemoteConfigValueType
    default_raw_value: str
    conditional_raw_values: dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))
        object.__setattr__(self, "key", self.key.strip())
        object.__setattr__(
            self,
            "conditional_raw_values",
            {
                str(name).strip(): str(value)
                for name, value in self.conditional_raw_values.items()
            },
        )

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

    @property
    def conditions_summary(self) -> str:
        """Condition values in a compact deterministic order."""
        if not self.conditional_raw_values:
            return "—"
        return " | ".join(
            f"{name}={self.conditional_raw_values[name]}"
            for name in sorted(self.conditional_raw_values)
        )


@dataclass(frozen=True)
class UIRemoteConfigKeyCreatePlanEntry:
    """One project where a new Remote Config key can be created."""

    target: FirebaseProjectTarget
    request: UIRemoteConfigKeyCreateRequest
    error: Optional[str] = None

    @property
    def status(self) -> str:
        """ready or error."""
        return "error" if self.error else "ready"

    @property
    def is_publishable(self) -> bool:
        """Whether this entry can be published."""
        return self.error is None

    @property
    def detail(self) -> str:
        """One-line explanation for the plan table."""
        if self.error:
            return self.error
        return (
            f"crear {self.request.key} ({self.request.type_label}) "
            f"default={self.request.default_raw_value}"
        )


@dataclass(frozen=True)
class UIRemoteConfigKeyCreateResult:
    """Outcome of validating or publishing one newly created key."""

    project_id: str
    key: str
    value_type: RemoteConfigValueType
    validated_only: bool
    etag: Optional[str]
    version: Optional["UIRemoteConfigVersion"]
    retried_after_conflict: bool = False

    def __post_init__(self) -> None:
        """Normalize value type strings left by older callers."""
        object.__setattr__(self, "value_type", normalize_value_type(self.value_type))

    @property
    def type_label(self) -> str:
        """Short user-facing type label."""
        return self.value_type.display_label

    @property
    def version_number(self) -> Optional[str]:
        """Version number Firebase assigned, when it published."""
        return self.version.version_number if self.version else None


@dataclass(frozen=True)
class UIRemoteConfigKeyCreateOutcome:
    """What happened when one new key was validated or published."""

    entry: UIRemoteConfigKeyCreatePlanEntry
    published: Optional["UIRemoteConfigKeyCreateResult"] = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """Whether Firebase accepted the create operation."""
        return self.error is None and self.published is not None

    @property
    def detail(self) -> str:
        """One-line result for the report table."""
        if self.error is not None:
            return self.error
        if self.published is None:
            return "sin publicar"
        if self.published.validated_only:
            return "validado"
        version = self.published.version_number or "?"
        if self.published.retried_after_conflict:
            return f"versión {version} (reintentada por ETag)"
        return f"versión {version}"


@dataclass(frozen=True)
class UIFanoutEntry:
    """One project's share of a multi-project change, before anything is published."""

    target: FirebaseProjectTarget
    change: Optional[UIRemoteConfigChange] = None
    error: Optional[str] = None

    @property
    def status(self) -> str:
        """ready, noop, or error."""
        if self.error is not None:
            return "error"
        if self.change is None or self.change.is_noop:
            return "noop"
        return "ready"

    @property
    def is_publishable(self) -> bool:
        """Whether publishing this entry would change anything."""
        return self.status == "ready"

    @property
    def detail(self) -> str:
        """One-line explanation for the plan table."""
        if self.error is not None:
            return self.error
        if self.change is None:
            return "sin cambio"
        if self.change.is_noop:
            return f"ya vale {self.change.new_raw_value}"
        old = self.change.old_raw_value
        return f"{old if old is not None else '(sin valor)'} -> {self.change.new_raw_value}"


@dataclass(frozen=True)
class UIFanoutOutcome:
    """What happened when one project's change was published."""

    target: FirebaseProjectTarget
    published: Optional["UIRemoteConfigPublishResult"] = None
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """Whether Firebase accepted the publish."""
        return self.error is None and self.published is not None

    @property
    def detail(self) -> str:
        """One-line result for the report table."""
        if self.error is not None:
            return self.error
        if self.published is None:
            return "sin publicar"
        version = self.published.version_number or "?"
        if self.published.retried_after_conflict:
            return f"versión {version} (reintentada por ETag)"
        return f"versión {version}"


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
