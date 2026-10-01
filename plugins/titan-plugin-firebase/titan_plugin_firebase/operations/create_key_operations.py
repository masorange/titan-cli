"""Plan and describe creating new Remote Config keys across projects."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from ..models.targets import FirebaseProjectTarget
from ..models.values import (
    RemoteConfigValueType,
    format_value_for_display,
    normalize_value_type,
)
from ..models.view import (
    UIRemoteConfigKeyCreateOutcome,
    UIRemoteConfigKeyCreatePlanEntry,
    UIRemoteConfigKeyCreateRequest,
)


def parse_condition_value_map(raw: Any) -> dict[str, str]:
    """
    Parse optional condition values from workflow data.

    A mapping is accepted directly. Strings can be a JSON object or a compact
    `condition=value` list split by commas or new lines.
    """
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return {
            str(name).strip(): str(value)
            for name, value in raw.items()
            if str(name).strip()
        }

    text = str(raw).strip()
    if not text:
        return {}

    if text.startswith("{"):
        parsed = json.loads(text)
        if not isinstance(parsed, Mapping):
            raise ValueError("conditional_values debe ser un objeto JSON.")
        return parse_condition_value_map(parsed)

    values: dict[str, str] = {}
    for chunk in text.replace("\n", ",").split(","):
        item = chunk.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError("conditional_values debe usar formato condition=value.")
        name, value = item.split("=", 1)
        condition_name = name.strip()
        if not condition_name:
            raise ValueError("conditional_values contiene una condición vacía.")
        values[condition_name] = value.strip()
    return values


def build_create_request(
    *,
    key: str,
    value_type: Any,
    default_value: str,
    conditional_values: Mapping[str, str] | None = None,
    description: str | None = None,
) -> UIRemoteConfigKeyCreateRequest:
    """Build the typed create request shared by every target project."""
    normalized_key = key.strip()
    if not normalized_key:
        raise ValueError("La clave de Remote Config es obligatoria.")

    normalized_type = normalize_value_type(value_type)
    if normalized_type == RemoteConfigValueType.UNKNOWN:
        raise ValueError(
            "El tipo de la nueva clave debe ser Bool, JSON, Number o String."
        )

    return UIRemoteConfigKeyCreateRequest(
        key=normalized_key,
        value_type=normalized_type,
        default_raw_value=str(default_value),
        conditional_raw_values=dict(conditional_values or {}),
        description=description.strip()
        if description and description.strip()
        else None,
    )


def targets_missing_key(
    targets: Iterable[FirebaseProjectTarget],
    profiles: Mapping[str, Any] | None,
    key: str,
) -> list[FirebaseProjectTarget]:
    """Return targets where the inventory says the key is missing."""
    ordered_targets = list(targets)
    if not profiles or key not in profiles:
        return ordered_targets

    profile = profiles.get(key)
    if not isinstance(profile, Mapping):
        return ordered_targets
    missing_ids = {
        str(project_id)
        for project_id in profile.get("missing_projects", []) or []
        if str(project_id).strip()
    }
    return [target for target in ordered_targets if target.project_id in missing_ids]


def select_create_targets(
    targets: Iterable[FirebaseProjectTarget],
    project_ids: Iterable[str],
) -> list[FirebaseProjectTarget]:
    """Keep targets selected by project id, preserving target order."""
    selected = {str(project_id) for project_id in project_ids}
    return [target for target in targets if target.project_id in selected]


def common_condition_names(
    project_conditions: Mapping[str, Any],
    targets: Iterable[FirebaseProjectTarget],
) -> list[str]:
    """Return condition names present in every selected target."""
    selected_targets = list(targets)
    if not selected_targets:
        return []

    common: set[str] | None = None
    for target in selected_targets:
        names = {
            str(condition.get("name"))
            for condition in project_conditions.get(target.project_id, []) or []
            if isinstance(condition, Mapping) and condition.get("name")
        }
        common = names if common is None else common & names

    return sorted(common or set())


def condition_availability(
    project_conditions: Mapping[str, Any],
    targets: Iterable[FirebaseProjectTarget],
) -> dict[str, int]:
    """Count how many selected projects declare each condition name."""
    counts: dict[str, int] = {}
    for target in targets:
        seen = {
            str(condition.get("name"))
            for condition in project_conditions.get(target.project_id, []) or []
            if isinstance(condition, Mapping) and condition.get("name")
        }
        for name in seen:
            counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def build_create_plan(
    targets: Iterable[FirebaseProjectTarget],
    request: UIRemoteConfigKeyCreateRequest,
) -> list[UIRemoteConfigKeyCreatePlanEntry]:
    """Build create entries for selected targets."""
    return [
        UIRemoteConfigKeyCreatePlanEntry(target=target, request=request)
        for target in targets
    ]


def select_create_entries(
    entries: Iterable[UIRemoteConfigKeyCreatePlanEntry],
    project_ids: Iterable[str],
) -> list[UIRemoteConfigKeyCreatePlanEntry]:
    """Keep publishable entries selected by project id."""
    selected = {str(project_id) for project_id in project_ids}
    return [
        entry
        for entry in entries
        if entry.is_publishable and entry.target.project_id in selected
    ]


def create_plan_summary(
    entries: Iterable[UIRemoteConfigKeyCreatePlanEntry],
) -> dict[str, int]:
    """Count ready and failed create-plan entries."""
    counts = {"ready": 0, "error": 0}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return counts


def create_outcome_summary(
    outcomes: Iterable[UIRemoteConfigKeyCreateOutcome],
) -> dict[str, int]:
    """Count accepted and failed projects."""
    published = 0
    failed = 0
    for outcome in outcomes:
        if outcome.succeeded:
            published += 1
        else:
            failed += 1
    return {"published": published, "failed": failed}


def describe_create_plan(
    entries: Iterable[UIRemoteConfigKeyCreatePlanEntry],
) -> list[list[str]]:
    """Build rows for the create plan table."""
    return [
        [
            entry.target.reference(),
            entry.status,
            entry.request.type_label,
            format_value_for_display(
                entry.request.default_raw_value,
                entry.request.value_type,
            ),
            _format_condition_values(entry.request),
            entry.error or "ok",
        ]
        for entry in entries
    ]


def describe_create_outcomes(
    outcomes: Iterable[UIRemoteConfigKeyCreateOutcome],
) -> list[list[str]]:
    """Build rows for the create result table."""
    return [
        [
            outcome.entry.target.reference(),
            "ok" if outcome.succeeded else "error",
            outcome.detail,
        ]
        for outcome in outcomes
    ]


def _format_condition_values(request: UIRemoteConfigKeyCreateRequest) -> str:
    """Render condition values using the request's declared type."""
    if not request.conditional_raw_values:
        return "—"
    return " | ".join(
        f"{name}={format_value_for_display(value, request.value_type)}"
        for name, value in sorted(request.conditional_raw_values.items())
    )
