"""
Resolving which Firebase project(s) a workflow acts on.

This plugin has no opinion about where a project ID comes from. One project is
either passed in or taken from `default_project`; several are passed in as a
list, which a caller that knows its own naming scheme — one project per brand,
per environment, per team — produces itself.

Pure functions: no context, no UI, no network.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from ..config import FirebasePluginConfig
from ..models.targets import FirebaseProjectTarget


class TargetResolutionError(ValueError):
    """Raised when nothing names a Firebase project to act on."""


def resolve_target(
    config: FirebasePluginConfig,
    *,
    project_id: Optional[str] = None,
    label: Optional[str] = None,
) -> FirebaseProjectTarget:
    """
    Resolve the single project to work on.

    Raises:
        TargetResolutionError: If neither the request nor the config names one.
    """
    chosen = (project_id or "").strip() or config.default_project
    if not chosen:
        raise TargetResolutionError(
            "No hay proyecto Firebase que usar. Pasa project_id al workflow o "
            "configura plugins.firebase.config.default_project."
        )
    return FirebaseProjectTarget(project_id=chosen, label=label)


def parse_project_ids(value: Any) -> list[str]:
    """
    Read a project list from workflow data.

    Accepts a list, or a comma- or whitespace-separated string so a workflow
    param can carry it. Order is preserved and duplicates are dropped, because
    publishing to the same project twice in one fan-out is never intended.
    """
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [part.strip() for part in value.replace(",", " ").split()]
    elif isinstance(value, (list, tuple, set)):
        candidates = [str(part).strip() for part in value]
    else:
        return []

    ordered: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in ordered:
            ordered.append(candidate)
    return ordered


def resolve_targets(
    project_ids: Iterable[str],
    labels: Optional[Mapping[str, str]] = None,
) -> list[FirebaseProjectTarget]:
    """
    Build targets for several projects, applying any caller-supplied labels.

    Raises:
        TargetResolutionError: If the list is empty.
    """
    ordered = parse_project_ids(list(project_ids))
    if not ordered:
        raise TargetResolutionError(
            "La lista de proyectos Firebase está vacía. Pasa project_ids al "
            "workflow, o produce firebase_project_ids en un paso anterior."
        )

    label_map = dict(labels or {})
    return [
        FirebaseProjectTarget(
            project_id=project_id,
            label=label_map.get(project_id),
        )
        for project_id in ordered
    ]
