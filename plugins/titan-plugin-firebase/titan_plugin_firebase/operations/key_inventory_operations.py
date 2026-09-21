"""Build read-only key inventories across Remote Config templates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..config import FirebaseConditionGroupConfig
from ..messages import msg
from ..models.targets import FirebaseProjectTarget
from ..models.values import (
    RemoteConfigValueSource,
    RemoteConfigValueType,
    display_value_types,
    infer_value_type,
)
from ..models.view import (
    UIRemoteConfigParameter,
    UIRemoteConfigTemplate,
    UIRemoteConfigValue,
)

TYPE_ORDER = {
    value_type.value: index for index, value_type in enumerate(RemoteConfigValueType)
}
SOURCE_ORDER = {
    source.value: index for index, source in enumerate(RemoteConfigValueSource)
}
VALUE_SUMMARY_MAX_LENGTH = 96
VALUE_FRAGMENT_MAX_LENGTH = 28
ENVIRONMENT_SUMMARY_MAX_LENGTH = 72
CONDITION_PREVIEW_LIMIT = 2


@dataclass(frozen=True)
class RemoteConfigParameterObservation:
    """Deterministic type observation for one key in one project."""

    project_id: str
    key: str
    declared_type: str
    inferred_types: list[str]
    effective_type: str
    decision: str
    value_count: int
    conditional_value_count: int
    value_sources: list[str]
    unsupported_value_sources: list[str]
    unsupported_value_count: int
    local_type_conflict: bool = False

    def to_metadata(self) -> dict[str, Any]:
        """Return a value-free payload suitable for workflow metadata."""
        return {
            "project_id": self.project_id,
            "key": self.key,
            "declared_type": self.declared_type,
            "inferred_types": self.inferred_types,
            "effective_type": self.effective_type,
            "decision": self.decision,
            "value_count": self.value_count,
            "conditional_value_count": self.conditional_value_count,
            "value_sources": self.value_sources,
            "unsupported_value_sources": self.unsupported_value_sources,
            "unsupported_value_count": self.unsupported_value_count,
            "local_type_conflict": self.local_type_conflict,
        }


@dataclass(frozen=True)
class RemoteConfigKeyProfile:
    """Cross-project normalization profile for one Remote Config key."""

    key: str
    present_projects: list[str]
    missing_projects: list[str]
    value_types: list[str]
    declared_value_types: list[str]
    inferred_value_types: list[str]
    observations: dict[str, RemoteConfigParameterObservation]

    @property
    def issues(self) -> list[str]:
        """Reasons this key is not safe to edit in one bulk operation."""
        issues: list[str] = []
        if self.missing_projects:
            issues.append("missing")
        if len(self.value_types) > 1:
            issues.append("type_conflict")
        if any(
            observation.local_type_conflict
            for observation in self.observations.values()
        ):
            issues.append("local_type_conflict")
        if any(
            observation.unsupported_value_count
            for observation in self.observations.values()
        ):
            issues.append("unsupported_value_source")
        if (
            not self.value_types
            or RemoteConfigValueType.UNKNOWN.value in self.value_types
        ):
            issues.append("unknown_type")
        return issues

    @property
    def is_bulk_safe(self) -> bool:
        """Whether every project can receive one typed value for this key."""
        return not self.issues

    @property
    def bulk_value_type(self) -> str | None:
        """The canonical type to use for a bulk edit, when one exists."""
        if not self.is_bulk_safe:
            return None
        return self.value_types[0]

    def to_metadata(self) -> dict[str, Any]:
        """Return a value-free payload suitable for workflow metadata."""
        return {
            "key": self.key,
            "bulk_safe": self.is_bulk_safe,
            "bulk_value_type": self.bulk_value_type,
            "issues": self.issues,
            "present_projects": self.present_projects,
            "missing_projects": self.missing_projects,
            "value_types": self.value_types,
            "declared_value_types": self.declared_value_types,
            "inferred_value_types": self.inferred_value_types,
            "observations": {
                project_id: observation.to_metadata()
                for project_id, observation in self.observations.items()
            },
        }


@dataclass(frozen=True)
class RemoteConfigKeyInventory:
    """Presence and type summary for a set of project templates."""

    keys: list[str]
    common_keys: list[str]
    key_types: dict[str, list[str]]
    key_profiles: dict[str, RemoteConfigKeyProfile]
    bulk_safe_keys: list[str]
    bulk_blocked_keys: dict[str, list[str]]
    missing_keys: dict[str, list[str]]
    type_conflicts: dict[str, list[str]]
    value_types: list[str]
    declared_value_types: list[str]
    unknown_type_keys: dict[str, list[str]]
    project_key_counts: dict[str, int]
    project_condition_counts: dict[str, int]

    @property
    def project_count(self) -> int:
        """Number of projects included in the inventory."""
        return len(self.project_key_counts)


@dataclass(frozen=True)
class RemoteConfigProjectKeyValueItem:
    """Expandable view model for one key in one Firebase project."""

    project_label: str
    key: str
    type_label: str
    description: str
    environment_summary: str
    value_summary: str
    value_rows: list[list[str]]
    json_details: list["RemoteConfigProjectKeyValueJsonDetail"]


@dataclass(frozen=True)
class RemoteConfigProjectKeyValueJsonDetail:
    """Structured JSON detail for one key value slot."""

    title: str
    value: Any


@dataclass(frozen=True)
class RemoteConfigKeyComparisonItem:
    """Expandable comparison of one key across every selected project."""

    key: str
    type_label: str
    present_count: int
    project_count: int
    status_label: str
    has_issues: bool
    description_lines: list[str]
    value_rows: list[list[str]]
    json_details: list[RemoteConfigProjectKeyValueJsonDetail]


def build_key_inventory(
    templates: Mapping[str, UIRemoteConfigTemplate],
) -> RemoteConfigKeyInventory:
    """Summarize key presence and deterministic value types per project."""
    parameters_by_project = {
        project_id: {parameter.key: parameter for parameter in template.parameters}
        for project_id, template in templates.items()
    }
    project_ids = list(parameters_by_project)
    keys = sorted(
        {key for parameters in parameters_by_project.values() for key in parameters}
    )
    key_profiles = {
        key: _key_profile(key, project_ids, parameters_by_project) for key in keys
    }
    common_keys = [
        key for key, profile in key_profiles.items() if not profile.missing_projects
    ]
    missing_keys = {
        project_id: [
            key
            for key, profile in key_profiles.items()
            if project_id in profile.missing_projects
        ]
        for project_id in project_ids
    }
    key_types = {key: profile.value_types for key, profile in key_profiles.items()}
    type_conflicts = {key: types for key, types in key_types.items() if len(types) > 1}
    value_types = sorted(
        {
            observation.effective_type
            for profile in key_profiles.values()
            for observation in profile.observations.values()
        },
        key=_type_sort_key,
    )
    declared_value_types = sorted(
        {
            observation.declared_type
            for profile in key_profiles.values()
            for observation in profile.observations.values()
        },
        key=_type_sort_key,
    )
    bulk_safe_keys = [
        key for key, profile in key_profiles.items() if profile.is_bulk_safe
    ]
    bulk_blocked_keys = {
        key: profile.issues
        for key, profile in key_profiles.items()
        if not profile.is_bulk_safe
    }
    unknown_key_sets = _unknown_type_keys(key_profiles, project_ids)
    project_key_counts = {
        project_id: len(template.parameters)
        for project_id, template in templates.items()
    }
    project_condition_counts = {
        project_id: len(template.conditions)
        for project_id, template in templates.items()
    }

    return RemoteConfigKeyInventory(
        keys=keys,
        common_keys=common_keys,
        key_types=key_types,
        key_profiles=key_profiles,
        bulk_safe_keys=bulk_safe_keys,
        bulk_blocked_keys=bulk_blocked_keys,
        missing_keys=missing_keys,
        type_conflicts=type_conflicts,
        value_types=value_types,
        declared_value_types=declared_value_types,
        unknown_type_keys=unknown_key_sets,
        project_key_counts=project_key_counts,
        project_condition_counts=project_condition_counts,
    )


def describe_project_inventory(
    targets: Iterable[FirebaseProjectTarget],
    inventory: RemoteConfigKeyInventory,
    failed_projects: Mapping[str, str],
) -> list[list[str]]:
    """Build rows for the per-project inventory table."""
    target_list = list(targets)
    target_labels = _comparison_target_labels(target_list)
    rows: list[list[str]] = []
    for target in target_list:
        error = failed_projects.get(target.project_id)
        if error is not None:
            rows.append(
                [
                    target_labels[target.project_id],
                    "-",
                    "-",
                    msg.Inventory.STATUS_ERROR.format(error=error),
                ]
            )
            continue
        rows.append(
            [
                target_labels[target.project_id],
                str(inventory.project_key_counts.get(target.project_id, 0)),
                str(inventory.project_condition_counts.get(target.project_id, 0)),
                msg.Inventory.STATUS_OK,
            ]
        )
    return rows


def describe_key_inventory(inventory: RemoteConfigKeyInventory) -> list[list[str]]:
    """Build rows for the cross-project key inventory table."""
    rows: list[list[str]] = []
    for key in inventory.keys:
        profile = inventory.key_profiles[key]
        missing_count = len(profile.missing_projects)
        present_count = len(profile.present_projects)
        types = profile.value_types or [RemoteConfigValueType.UNKNOWN.value]
        status_parts = []
        if "type_conflict" in profile.issues:
            status_parts.append("type conflict")
        if "local_type_conflict" in profile.issues:
            status_parts.append("mixed values")
        if "unsupported_value_source" in profile.issues:
            status_parts.append("managed value")
        if "unknown_type" in profile.issues:
            status_parts.append("unknown type")
        if missing_count:
            status_parts.append(f"missing in {missing_count}")
        status = ", ".join(status_parts) or "ok"

        rows.append(
            [
                key,
                f"{present_count}/{inventory.project_count}",
                " / ".join(display_value_types(types)),
                status,
            ]
        )
    return rows


def describe_key_comparison_items(
    templates: Mapping[str, UIRemoteConfigTemplate],
    targets: Iterable[FirebaseProjectTarget],
    inventory: RemoteConfigKeyInventory,
    condition_group: FirebaseConditionGroupConfig | None = None,
    failed_projects: Mapping[str, str] | None = None,
) -> list[RemoteConfigKeyComparisonItem]:
    """Build one key-centric comparison item across all selected projects."""
    target_list = list(targets)
    failures = failed_projects or {}
    target_labels = _comparison_target_labels(target_list)
    parameters_by_project = {
        project_id: {parameter.key: parameter for parameter in template.parameters}
        for project_id, template in templates.items()
    }
    items: list[RemoteConfigKeyComparisonItem] = []

    for key in inventory.keys:
        profile = inventory.key_profiles[key]
        value_rows: list[list[str]] = []
        json_details: list[RemoteConfigProjectKeyValueJsonDetail] = []
        descriptions: list[tuple[str, str | None]] = []

        for target in target_list:
            project_label = target_labels[target.project_id]
            project_environment = (
                target.environment.upper() if target.environment else "—"
            )
            if target.project_id in failures:
                value_rows.append(
                    [
                        project_label,
                        project_environment,
                        "—",
                        msg.Inventory.VALUE_UNREAD,
                        "—",
                        "—",
                    ]
                )
                continue

            parameter = parameters_by_project.get(target.project_id, {}).get(key)
            if parameter is None:
                value_rows.append(
                    [
                        project_label,
                        project_environment,
                        "—",
                        msg.Inventory.VALUE_MISSING,
                        "—",
                        "—",
                    ]
                )
                continue

            descriptions.append((project_label, parameter.description))
            slots = _parameter_value_slots(parameter, condition_group)
            if not slots:
                value_rows.append(
                    [
                        project_label,
                        project_environment,
                        "—",
                        msg.Inventory.VALUE_NOT_IN_VIEW,
                        "—",
                        "—",
                    ]
                )
                continue

            for index, (environment, value) in enumerate(slots):
                value_rows.append(
                    [
                        project_label if index == 0 else "",
                        project_environment if index == 0 else "",
                        environment,
                        _value_table_display(value),
                        value.source_label,
                        (
                            msg.Inventory.EDITABLE_YES
                            if value.is_titan_editable
                            else msg.Inventory.EDITABLE_NO
                        ),
                    ]
                )
                parsed_json = _json_detail_value(value)
                if parsed_json is not None:
                    json_details.append(
                        RemoteConfigProjectKeyValueJsonDetail(
                            title=f"{project_label} · {environment}",
                            value=parsed_json,
                        )
                    )

        status_parts = _comparison_status_parts(profile, failures)
        types = profile.value_types or [RemoteConfigValueType.UNKNOWN.value]
        items.append(
            RemoteConfigKeyComparisonItem(
                key=key,
                type_label=" / ".join(display_value_types(types)),
                present_count=len(profile.present_projects),
                project_count=len(target_list),
                status_label=", ".join(status_parts) or msg.Inventory.STATUS_OK,
                has_issues=bool(status_parts),
                description_lines=_comparison_description_lines(descriptions),
                value_rows=value_rows,
                json_details=json_details,
            )
        )

    return items


def describe_project_key_values(
    templates: Mapping[str, UIRemoteConfigTemplate],
    targets: Iterable[FirebaseProjectTarget],
    condition_group: FirebaseConditionGroupConfig | None = None,
) -> list[list[str]]:
    """Build compact one-line rows with each key's values per project."""
    rows: list[list[str]] = []
    target_labels = {target.project_id: _target_label(target) for target in targets}

    for project_id, template in templates.items():
        project_label = target_labels.get(project_id, project_id)
        for parameter in template.parameters:
            if not _parameter_value_slots(parameter, condition_group):
                continue
            rows.append(
                [
                    project_label,
                    parameter.key,
                    _parameter_environments(parameter, condition_group),
                    _parameter_value_summary(parameter, condition_group),
                ]
            )
    return rows


def describe_project_key_value_items(
    templates: Mapping[str, UIRemoteConfigTemplate],
    targets: Iterable[FirebaseProjectTarget],
    condition_group: FirebaseConditionGroupConfig | None = None,
) -> list[RemoteConfigProjectKeyValueItem]:
    """Build expandable items with each key's values per project."""
    items: list[RemoteConfigProjectKeyValueItem] = []
    target_labels = {target.project_id: _target_label(target) for target in targets}

    for project_id, template in templates.items():
        project_label = target_labels.get(project_id, project_id)
        for parameter in template.parameters:
            slots = _parameter_value_slots(parameter, condition_group)
            if not slots:
                continue
            items.append(
                RemoteConfigProjectKeyValueItem(
                    project_label=project_label,
                    key=parameter.key,
                    type_label=parameter.type_label,
                    description=parameter.description or "",
                    environment_summary=_parameter_environments(
                        parameter,
                        condition_group,
                    ),
                    value_summary=_parameter_value_summary(
                        parameter,
                        condition_group,
                    ),
                    value_rows=[
                        [
                            name,
                            _value_table_display(value),
                            value.source_label,
                            "si" if value.is_titan_editable else "no",
                        ]
                        for name, value in slots
                    ],
                    json_details=[
                        RemoteConfigProjectKeyValueJsonDetail(name, parsed)
                        for name, value in slots
                        if (parsed := _json_detail_value(value)) is not None
                    ],
                )
            )
    return items


def _target_label(target: FirebaseProjectTarget) -> str:
    """Render the configured brand as the primary inventory identity."""
    return target.brand or target.label or target.project_id


def _comparison_target_labels(
    targets: Iterable[FirebaseProjectTarget],
) -> dict[str, str]:
    """Use brand names, adding the configured label only for true duplicates."""
    target_list = list(targets)
    base_labels = {
        target.project_id: target.brand or target.label or target.project_id
        for target in target_list
    }
    identity_counts = {
        (base_labels[target.project_id], target.environment): sum(
            1
            for candidate in target_list
            if (
                base_labels[candidate.project_id],
                candidate.environment,
            )
            == (base_labels[target.project_id], target.environment)
        )
        for target in target_list
    }
    labels: dict[str, str] = {}
    for target in target_list:
        label = base_labels[target.project_id]
        identity = (label, target.environment)
        if (
            identity_counts[identity] > 1
            and target.label
            and target.label != label
        ):
            label = f"{label} · {target.label}"
        labels[target.project_id] = label
    return labels


def _comparison_status_parts(
    profile: RemoteConfigKeyProfile,
    failed_projects: Mapping[str, str],
) -> list[str]:
    """Translate profile blockers into compact labels for the key header."""
    parts: list[str] = []
    if "type_conflict" in profile.issues:
        parts.append(msg.Inventory.STATUS_TYPE_CONFLICT)
    if "local_type_conflict" in profile.issues:
        parts.append(msg.Inventory.STATUS_MIXED_VALUES)
    if "unsupported_value_source" in profile.issues:
        parts.append(msg.Inventory.STATUS_NOT_EDITABLE)
    if "unknown_type" in profile.issues:
        parts.append(msg.Inventory.STATUS_UNKNOWN_TYPE)
    if profile.missing_projects:
        parts.append(
            msg.Inventory.STATUS_MISSING.format(
                count=len(profile.missing_projects)
            )
        )
    if failed_projects:
        parts.append(
            msg.Inventory.STATUS_UNREAD.format(count=len(failed_projects))
        )
    return parts


def _comparison_description_lines(
    descriptions: Iterable[tuple[str, str | None]],
) -> list[str]:
    """Show one shared description or identify project-specific differences."""
    entries = list(descriptions)
    distinct = list(
        dict.fromkeys(description for _label, description in entries if description)
    )
    if not distinct:
        return []
    if len(distinct) == 1 and all(
        description in (None, distinct[0]) for _label, description in entries
    ):
        return [distinct[0]]
    return [
        msg.Inventory.DESCRIPTIONS_DIFFER,
        *[
            f"{label}: {description or '—'}"
            for label, description in entries
        ],
    ]


def _parameter_environments(
    parameter: UIRemoteConfigParameter,
    condition_group: FirebaseConditionGroupConfig | None = None,
) -> str:
    """Render the default plus condition names where the key has values."""
    names = [name for name, _value in _parameter_value_slots(parameter, condition_group)]
    return _compact_cell(", ".join(names), ENVIRONMENT_SUMMARY_MAX_LENGTH)


def _parameter_value_summary(
    parameter: UIRemoteConfigParameter,
    condition_group: FirebaseConditionGroupConfig | None = None,
) -> str:
    """Render a parameter's values as a compact table-safe preview."""
    slots = _parameter_value_slots(parameter, condition_group)
    if not slots:
        summary = f"{parameter.type_label} · sin valores en esta agrupacion"
        return _compact_cell(summary, VALUE_SUMMARY_MAX_LENGTH)

    parts: list[str] = []
    for name, value in slots[:CONDITION_PREVIEW_LIMIT]:
        parts.append(
            f"{name}="
            f"{_compact_cell(value.display_value, VALUE_FRAGMENT_MAX_LENGTH)}"
        )
    remaining = len(slots) - CONDITION_PREVIEW_LIMIT
    prefix = f"{parameter.type_label} · "
    values = ", ".join(parts)
    if remaining > 0:
        suffix = f", +{remaining} mas"
        available = VALUE_SUMMARY_MAX_LENGTH - len(prefix) - len(suffix)
        values = _compact_cell(values, max(1, available))
        summary = f"{prefix}{values}{suffix}"
    else:
        summary = f"{prefix}{values}"
    return _compact_cell(summary, VALUE_SUMMARY_MAX_LENGTH)


def _value_table_display(value: UIRemoteConfigValue) -> str:
    """Render one value for the compact detail table."""
    if value.raw_value is None:
        return "—"
    parsed_json = _json_detail_value(value)
    if parsed_json is not None:
        return _json_value_summary(parsed_json)
    if value.value_type.preserves_whitespace:
        return value.raw_value
    return value.display_value


def _json_detail_value(value: UIRemoteConfigValue) -> Any | None:
    """Return parsed structured JSON when the value can be rendered as a tree."""
    if value.value_type == RemoteConfigValueType.JSON:
        try:
            parsed = json.loads(value.raw_value.strip())
        except (AttributeError, ValueError):
            return None
        if isinstance(parsed, (dict, list)):
            return parsed
    return None


def _json_value_summary(value: Any) -> str:
    """Render a short table-safe summary of a JSON container."""
    if isinstance(value, dict):
        count = len(value)
        suffix = "clave" if count == 1 else "claves"
        return f"objeto · {count} {suffix}"
    if isinstance(value, list):
        count = len(value)
        suffix = "elemento" if count == 1 else "elementos"
        return f"array · {count} {suffix}"
    return "JSON"


def _parameter_value_slots(
    parameter: UIRemoteConfigParameter,
    condition_group: FirebaseConditionGroupConfig | None,
) -> list[tuple[str, UIRemoteConfigValue]]:
    """Return the value slots selected for display."""
    slots: list[tuple[str, UIRemoteConfigValue]] = []
    if condition_group is None or condition_group.include_default:
        slots.append(("default", parameter.default_value))
    for condition_name in sorted(parameter.conditional_values):
        if condition_group is None or _condition_matches_group(
            condition_name,
            condition_group,
        ):
            slots.append((condition_name, parameter.conditional_values[condition_name]))
    return slots


def _condition_matches_group(
    condition_name: str,
    condition_group: FirebaseConditionGroupConfig,
) -> bool:
    """Return whether a Remote Config condition belongs to a configured view."""
    normalized = condition_name.casefold()
    if any(condition.casefold() == normalized for condition in condition_group.conditions):
        return True
    if any(
        normalized.startswith(prefix.casefold())
        for prefix in condition_group.condition_prefixes
    ):
        return True
    return any(
        fragment.casefold() in normalized
        for fragment in condition_group.condition_contains
    )


def _compact_cell(value: str, max_length: int) -> str:
    """Collapse whitespace and cap long values so DataTable rows stay one line."""
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= max_length:
        return collapsed
    if max_length <= 1:
        return collapsed[:max_length]
    return f"{collapsed[: max_length - 1]}…"


def _key_profile(
    key: str,
    project_ids: Iterable[str],
    parameters_by_project: Mapping[str, Mapping[str, UIRemoteConfigParameter]],
) -> RemoteConfigKeyProfile:
    """Build the normalized profile for one key."""
    present_projects: list[str] = []
    missing_projects: list[str] = []
    observations: dict[str, RemoteConfigParameterObservation] = {}

    for project_id in project_ids:
        parameter = parameters_by_project[project_id].get(key)
        if parameter is None:
            missing_projects.append(project_id)
            continue
        present_projects.append(project_id)
        observations[project_id] = observe_parameter(project_id, parameter)

    return RemoteConfigKeyProfile(
        key=key,
        present_projects=present_projects,
        missing_projects=missing_projects,
        value_types=_sort_type_names(
            observation.effective_type for observation in observations.values()
        ),
        declared_value_types=_sort_type_names(
            observation.declared_type for observation in observations.values()
        ),
        inferred_value_types=_sort_type_names(
            inferred_type
            for observation in observations.values()
            for inferred_type in observation.inferred_types
        ),
        observations=observations,
    )


def observe_parameter(
    project_id: str,
    parameter: UIRemoteConfigParameter,
) -> RemoteConfigParameterObservation:
    """
    Classify one parameter from stable inputs only.

    Firebase stores values as strings. A declared `valueType` is authoritative;
    legacy untyped parameters are inferred from every explicit value instead of
    from the first one, so mixed defaults/conditionals become an explicit
    blocker rather than a hidden ordering accident.
    """
    declared_type = parameter.declared_value_type.value
    values = _parameter_values(parameter)
    inferred_types = _sort_type_names(
        infer_value_type(value.raw_value).value
        for value in values
        if infer_value_type(value.raw_value) != RemoteConfigValueType.UNKNOWN
    )
    unsupported_values = [value for value in values if not value.is_titan_editable]

    if parameter.declared_value_type != RemoteConfigValueType.UNKNOWN:
        effective_type = declared_type
        decision = "declared"
        local_type_conflict = False
    elif len(inferred_types) == 1:
        effective_type = inferred_types[0]
        decision = "inferred"
        local_type_conflict = False
    elif len(inferred_types) > 1:
        effective_type = RemoteConfigValueType.UNKNOWN.value
        decision = "mixed_inferred"
        local_type_conflict = True
    else:
        effective_type = RemoteConfigValueType.UNKNOWN.value
        decision = "unknown"
        local_type_conflict = False

    return RemoteConfigParameterObservation(
        project_id=project_id,
        key=parameter.key,
        declared_type=declared_type,
        inferred_types=inferred_types,
        effective_type=effective_type,
        decision=decision,
        value_count=len(values),
        conditional_value_count=len(parameter.conditional_values),
        value_sources=_sort_source_names(value.source.value for value in values),
        unsupported_value_sources=_sort_source_names(
            value.source.value for value in unsupported_values
        ),
        unsupported_value_count=len(unsupported_values),
        local_type_conflict=local_type_conflict,
    )


def key_profiles_to_metadata(
    profiles: Mapping[str, RemoteConfigKeyProfile],
) -> dict[str, dict[str, Any]]:
    """Serialize key profiles for workflow metadata without exposing values."""
    return {key: profile.to_metadata() for key, profile in profiles.items()}


def parameter_values_to_metadata(
    parameter: UIRemoteConfigParameter,
) -> dict[str, Any]:
    """Serialize one parameter's default and condition values for workflows."""
    return {
        "key": parameter.key,
        "value_type": parameter.value_type.value,
        "type_label": parameter.type_label,
        "default_value": _value_to_metadata(parameter.default_value),
        "conditional_values": {
            name: _value_to_metadata(parameter.conditional_values[name])
            for name in sorted(parameter.conditional_values)
        },
    }


def template_key_values_to_metadata(
    template: UIRemoteConfigTemplate,
) -> dict[str, dict[str, Any]]:
    """Serialize every parameter value in one template, keyed by parameter name."""
    return {
        parameter.key: parameter_values_to_metadata(parameter)
        for parameter in template.parameters
    }


def project_key_values_to_metadata(
    templates: Mapping[str, UIRemoteConfigTemplate],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Serialize every parameter value per project for downstream workflows."""
    return {
        project_id: template_key_values_to_metadata(template)
        for project_id, template in templates.items()
    }


def project_conditions_to_metadata(
    templates: Mapping[str, UIRemoteConfigTemplate],
) -> dict[str, list[dict[str, str | None]]]:
    """Serialize condition names and display context per project."""
    return {
        project_id: [
            {
                "name": condition.name,
                "expression": condition.expression,
                "display_expression": condition.display_expression,
                "tag_color": condition.tag_color,
            }
            for condition in template.conditions
        ]
        for project_id, template in templates.items()
    }


def _unknown_type_keys(
    profiles: Mapping[str, RemoteConfigKeyProfile],
    project_ids: Iterable[str],
) -> dict[str, list[str]]:
    """Return projects whose keys could not be typed deterministically."""
    return {
        project_id: [
            key
            for key, profile in profiles.items()
            if (
                project_id in profile.observations
                and profile.observations[project_id].effective_type
                == RemoteConfigValueType.UNKNOWN.value
            )
        ]
        for project_id in project_ids
    }


def _parameter_values(
    parameter: UIRemoteConfigParameter,
) -> list[UIRemoteConfigValue]:
    """Return values in a deterministic order: default, then conditions by name."""
    values: list[UIRemoteConfigValue] = []
    if parameter.default_value is not None:
        values.append(parameter.default_value)
    values.extend(
        parameter.conditional_values[name]
        for name in sorted(parameter.conditional_values)
    )
    return values


def _value_to_metadata(value: UIRemoteConfigValue | None) -> dict[str, Any]:
    """Return a structured value payload with both raw and display forms."""
    if value is None:
        return {
            "raw_value": None,
            "display_value": "—",
            "value_type": RemoteConfigValueType.UNKNOWN.value,
            "type_label": RemoteConfigValueType.UNKNOWN.display_label,
            "use_in_app_default": False,
            "value_source": RemoteConfigValueSource.UNKNOWN.value,
            "source_label": RemoteConfigValueSource.UNKNOWN.display_label,
            "editable": False,
        }
    return {
        "raw_value": value.raw_value,
        "display_value": value.display_value,
        "value_type": value.value_type.value,
        "type_label": value.type_label,
        "use_in_app_default": value.use_in_app_default,
        "value_source": value.source.value,
        "source_label": value.source_label,
        "editable": value.is_titan_editable,
    }


def _sort_type_names(values: Iterable[str]) -> list[str]:
    """Deduplicate and sort type names by Firebase's canonical enum order."""
    return sorted(set(values), key=_type_sort_key)


def _type_sort_key(value: str) -> tuple[int, str]:
    """Sort known enum values first, then unknown future names deterministically."""
    return (TYPE_ORDER.get(value, len(TYPE_ORDER)), value)


def _sort_source_names(values: Iterable[str]) -> list[str]:
    """Deduplicate and sort value source names by Firebase's enum order."""
    return sorted(set(values), key=_source_sort_key)


def _source_sort_key(value: str) -> tuple[int, str]:
    """Sort known value source enum names first."""
    return (SOURCE_ORDER.get(value, len(SOURCE_ORDER)), value)
