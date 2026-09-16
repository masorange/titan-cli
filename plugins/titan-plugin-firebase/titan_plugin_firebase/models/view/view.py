"""UI models: pre-formatted for rendering, never used for network payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..targets import FirebaseProjectTarget
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
class UIRemoteConfigChangeSet:
    """
    One value written to one or more targets of the same parameter.

    A publish replaces the whole template, so writing the same value to the
    default value and to three conditions is one publish and therefore one
    Remote Config version — not four. That is why the change set, and not the
    single change, is the unit the write path carries.
    """

    key: str
    value_type: RemoteConfigValueType
    new_raw_value: str
    changes: tuple[UIRemoteConfigChange, ...] = ()

    @property
    def pending(self) -> tuple[UIRemoteConfigChange, ...]:
        """The changes that would actually alter something."""
        return tuple(change for change in self.changes if not change.is_noop)

    @property
    def is_noop(self) -> bool:
        """Whether publishing this set would alter nothing."""
        return not self.pending

    @property
    def target_labels(self) -> list[str]:
        """Targets this set writes, in selection order."""
        return [change.target_label for change in self.changes]

    def describe(self, *, max_targets: int = 4) -> str:
        """
        One-line summary, published as the Remote Config version description.

        It appears in the version history next to the author, so it names the
        key, the value, and which targets got it.
        """
        pending = self.pending
        labels = [change.target_label for change in pending]
        if len(labels) > max_targets:
            shown = ", ".join(labels[:max_targets])
            targets = f"{shown} y {len(labels) - max_targets} más"
        else:
            targets = ", ".join(labels)

        value = " ".join(self.new_raw_value.split())
        if len(value) > 80:
            value = f"{value[:79]}…"
        return f"Titan: {self.key} = {value} [{targets}]"


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
    change_set: Optional["UIRemoteConfigChangeSet"] = None
    retried_after_conflict: bool = False

    @property
    def version_number(self) -> Optional[str]:
        """Version number Firebase assigned, when it published."""
        return self.version.version_number if self.version else None


@dataclass(frozen=True)
class UIFanoutEntry:
    """One project's share of a multi-project change, before anything is published."""

    target: FirebaseProjectTarget
    change_set: Optional["UIRemoteConfigChangeSet"] = None
    error: Optional[str] = None

    @property
    def status(self) -> str:
        """ready, noop, or error."""
        if self.error is not None:
            return "error"
        if self.change_set is None or self.change_set.is_noop:
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
        if self.change_set is None:
            return "sin cambio"
        if self.change_set.is_noop:
            return f"ya vale {self.change_set.new_raw_value}"
        pending = self.change_set.pending
        targets = ", ".join(change.target_label for change in pending)
        return f"{len(pending)} destino(s): {targets}"


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
