"""Plan missing Remote Config key copies across projects."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..models.targets import FirebaseProjectTarget
from ..models.values import (
    RemoteConfigValueType,
    display_value_types,
    normalize_value_type,
)
from ..models.view import (
    UIRemoteConfigKeyCopyOutcome,
    UIRemoteConfigKeyCopyPlanEntry,
)


def copyable_key_names(
    profiles: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Return keys that exist somewhere and are missing somewhere else."""
    return sorted(
        key
        for key, profile in profiles.items()
        if _profile_list(profile, "present_projects")
        and _profile_list(profile, "missing_projects")
    )


def describe_copy_candidate(profile: Mapping[str, Any]) -> str:
    """Describe why a key can be copied and whether it needs care."""
    missing_count = len(_profile_list(profile, "missing_projects"))
    present_count = len(_profile_list(profile, "present_projects"))
    value_types = _profile_list(profile, "value_types")
    type_label = (
        " / ".join(display_value_types(value_types)) if value_types else "Unknown"
    )
    issues = _profile_list(profile, "issues")
    parts = [
        f"falta en {missing_count}",
        f"existe en {present_count}",
        type_label,
    ]
    if issues:
        parts.append(f"revisar: {', '.join(issues)}")
    return " · ".join(parts)


def target_map(
    targets: Iterable[FirebaseProjectTarget],
) -> dict[str, FirebaseProjectTarget]:
    """Index targets by project ID."""
    return {target.project_id: target for target in targets}


def targets_for_project_ids(
    targets: Iterable[FirebaseProjectTarget],
    project_ids: Iterable[str],
) -> list[FirebaseProjectTarget]:
    """Resolve project IDs to targets while preserving the provided order."""
    by_id = target_map(targets)
    return [by_id[project_id] for project_id in project_ids if project_id in by_id]


def source_value_type(
    profile: Mapping[str, Any],
    source_project_id: str,
) -> RemoteConfigValueType:
    """Return the source project's deterministic effective type."""
    observations = profile.get("observations", {})
    if not isinstance(observations, Mapping):
        return RemoteConfigValueType.UNKNOWN
    observation = observations.get(source_project_id)
    if not isinstance(observation, Mapping):
        return RemoteConfigValueType.UNKNOWN
    return normalize_value_type(observation.get("effective_type"))


def source_has_local_type_conflict(
    profile: Mapping[str, Any],
    source_project_id: str,
) -> bool:
    """Return whether the source key has mixed inferred values."""
    observations = profile.get("observations", {})
    if not isinstance(observations, Mapping):
        return False
    observation = observations.get(source_project_id)
    return (
        isinstance(observation, Mapping)
        and observation.get("local_type_conflict") is True
    )


def source_has_unsupported_value_source(
    profile: Mapping[str, Any],
    source_project_id: str,
) -> bool:
    """Return whether the source contains a value Titan must not copy."""
    observations = profile.get("observations", {})
    if not isinstance(observations, Mapping):
        return False
    observation = observations.get(source_project_id)
    if not isinstance(observation, Mapping):
        return False
    return int(observation.get("unsupported_value_count") or 0) > 0


def build_key_copy_plan(
    *,
    key: str,
    source: FirebaseProjectTarget,
    destinations: Iterable[FirebaseProjectTarget],
    value_type: RemoteConfigValueType,
) -> list[UIRemoteConfigKeyCopyPlanEntry]:
    """Build the plan entries for copying one key to missing projects."""
    return [
        UIRemoteConfigKeyCopyPlanEntry(
            key=key,
            source=source,
            target=destination,
            value_type=value_type,
        )
        for destination in destinations
    ]


def select_key_copy_entries(
    entries: Iterable[UIRemoteConfigKeyCopyPlanEntry],
    project_ids: Iterable[str],
) -> list[UIRemoteConfigKeyCopyPlanEntry]:
    """Keep the entries the user chose, preserving plan order."""
    selected = set(project_ids)
    return [entry for entry in entries if entry.target.project_id in selected]


def key_copy_outcome_summary(
    outcomes: Iterable[UIRemoteConfigKeyCopyOutcome],
) -> dict[str, int]:
    """Count copied and failed projects."""
    copied = 0
    failed = 0
    for outcome in outcomes:
        if outcome.succeeded:
            copied += 1
        else:
            failed += 1
    return {"copied": copied, "failed": failed}


def describe_key_copy_plan(
    entries: Iterable[UIRemoteConfigKeyCopyPlanEntry],
) -> list[list[str]]:
    """Build the rows of the copy plan table."""
    return [
        [
            entry.target.reference(),
            entry.key,
            entry.value_type.display_label,
            entry.source.reference(),
        ]
        for entry in entries
    ]


def describe_key_copy_outcomes(
    outcomes: Iterable[UIRemoteConfigKeyCopyOutcome],
) -> list[list[str]]:
    """Build the rows of the copy result table."""
    return [
        [
            outcome.entry.target.reference(),
            "ok" if outcome.succeeded else "error",
            outcome.detail,
        ]
        for outcome in outcomes
    ]


def _profile_list(profile: Mapping[str, Any], key: str) -> list[str]:
    """Return a profile list field as strings."""
    value = profile.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
