"""
Resolving which Firebase project(s) a workflow acts on.

This plugin has no opinion about project naming schemes. It accepts Firebase
project IDs directly or through configured project sets, and carries optional
repository-owned metadata such as brand, environment and groups so workflows can
filter safely without hardcoding business rules.

Pure functions: no context, no UI, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional

from ..config import FirebaseConfiguredProject, FirebasePluginConfig
from ..models.targets import FirebaseProjectTarget


class TargetResolutionError(ValueError):
    """Raised when nothing names a Firebase project to act on."""


@dataclass(frozen=True)
class ProjectSetResolution:
    """Resolved targets from one configured project set."""

    name: str
    groups: list[str]
    environments: list[str]
    default_environment: str | None
    targets: list[FirebaseProjectTarget]


@dataclass(frozen=True)
class ConfiguredProjectContext:
    """Configured project plus metadata inherited from its project set."""

    project: FirebaseConfiguredProject
    default_environment: str | None


def resolve_target(
    config: FirebasePluginConfig,
    *,
    project_id: Optional[str] = None,
    label: Optional[str] = None,
    brand: Optional[str] = None,
    environment: Optional[str] = None,
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
    configured_context = find_configured_project_context(config, chosen)
    configured = configured_context.project if configured_context else None
    inherited_environment = (
        configured_context.default_environment if configured_context else None
    )
    return FirebaseProjectTarget(
        project_id=chosen,
        label=label or (configured.label if configured else None),
        brand=brand or (configured.brand if configured else None),
        environment=environment
        or (configured.environment if configured else None)
        or inherited_environment,
        groups=configured.groups if configured else [],
    )


def resolve_project_set(
    config: FirebasePluginConfig,
    *,
    project_set: Optional[str] = None,
    groups: Any = None,
    environments: Any = None,
) -> ProjectSetResolution | None:
    """
    Resolve targets from a named project set in plugin config.

    Returns None when neither the request nor config names a project set. Raises
    TargetResolutionError when a named set is missing or a group filter removes
    every project.
    """
    explicit_name = (project_set or "").strip()
    set_name = explicit_name or config.default_project_set
    if not set_name:
        return None

    configured_set = config.project_sets.get(set_name)
    if configured_set is None:
        raise TargetResolutionError(
            f"No existe el project_set de Firebase '{set_name}' en "
            "plugins.firebase.config.project_sets."
        )

    group_names = parse_group_names(groups)
    environment_names = parse_environment_names(environments)
    set_default_environment = (
        configured_set.default_environment or config.default_environment
    )
    configured_projects = configured_set.projects
    if group_names:
        configured_projects = [
            project
            for project in configured_projects
            if any(group in project.groups for group in group_names)
        ]
    if environment_names:
        configured_projects = [
            project
            for project in configured_projects
            if (project.environment or set_default_environment) in environment_names
        ]

    if not configured_projects:
        filters = []
        if group_names:
            filters.append(f"grupos {', '.join(group_names)}")
        if environment_names:
            filters.append(f"entornos {', '.join(environment_names)}")
        suffix = f" para {' y '.join(filters)}" if filters else ""
        raise TargetResolutionError(
            f"El project_set de Firebase '{set_name}' no contiene proyectos{suffix}."
        )

    return ProjectSetResolution(
        name=set_name,
        groups=group_names,
        environments=environment_names,
        default_environment=set_default_environment,
        targets=[
            FirebaseProjectTarget(
                project_id=project.project_id,
                label=project.label,
                brand=project.brand,
                environment=project.environment or set_default_environment,
                groups=project.groups,
            )
            for project in configured_projects
        ],
    )


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


def parse_group_names(value: Any) -> list[str]:
    """Read project-set group filters from workflow data."""
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
        group = candidate.casefold()
        if group and group not in ordered:
            ordered.append(group)
    return ordered


def parse_environment_names(value: Any) -> list[str]:
    """Read environment filters from workflow data."""
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
        environment = candidate.casefold()
        if environment and environment not in ordered:
            ordered.append(environment)
    return ordered


def resolve_targets(
    project_ids: Iterable[str],
    labels: Optional[Mapping[str, str]] = None,
    brands: Optional[Mapping[str, str]] = None,
    environments: Optional[Mapping[str, str]] = None,
    groups: Optional[Mapping[str, Any]] = None,
    config: Optional[FirebasePluginConfig] = None,
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
    brand_map = dict(brands or {})
    environment_map = dict(environments or {})
    group_map = dict(groups or {})
    return [
        _target_from_project_id(
            project_id,
            label=label_map.get(project_id),
            brand=brand_map.get(project_id),
            environment=environment_map.get(project_id),
            groups=group_map.get(project_id),
            config=config,
        )
        for project_id in ordered
    ]


def find_configured_project(
    config: FirebasePluginConfig,
    project_id: str,
) -> FirebaseConfiguredProject | None:
    """Find metadata for a configured project ID, preferring the default set."""
    context = find_configured_project_context(config, project_id)
    return context.project if context else None


def find_configured_project_context(
    config: FirebasePluginConfig,
    project_id: str,
) -> ConfiguredProjectContext | None:
    """Find a configured project and the environment inherited from its set."""
    set_names = list(config.project_sets)
    if config.default_project_set in config.project_sets:
        set_names.remove(config.default_project_set)
        set_names.insert(0, config.default_project_set)

    for set_name in set_names:
        configured_set = config.project_sets[set_name]
        default_environment = (
            configured_set.default_environment or config.default_environment
        )
        for project in configured_set.projects:
            if project.project_id == project_id:
                return ConfiguredProjectContext(
                    project=project,
                    default_environment=default_environment,
                )
    return None


def filter_targets_by_environment(
    targets: Iterable[FirebaseProjectTarget],
    environments: Any,
) -> list[FirebaseProjectTarget]:
    """Keep only targets whose configured environment matches the filter."""
    environment_names = parse_environment_names(environments)
    ordered = list(targets)
    if not environment_names:
        return ordered
    return [target for target in ordered if target.environment in environment_names]


def target_environments(targets: Iterable[FirebaseProjectTarget]) -> list[str]:
    """Return known environments represented in target order."""
    ordered: list[str] = []
    for target in targets:
        if target.environment and target.environment not in ordered:
            ordered.append(target.environment)
    return ordered


def _target_from_project_id(
    project_id: str,
    *,
    label: Optional[str],
    brand: Optional[str],
    environment: Optional[str],
    groups: Any,
    config: Optional[FirebasePluginConfig],
) -> FirebaseProjectTarget:
    """Build one target, enriching it from config when possible."""
    configured_context = (
        find_configured_project_context(config, project_id) if config else None
    )
    configured = configured_context.project if configured_context else None
    inherited_environment = (
        configured_context.default_environment if configured_context else None
    )
    return FirebaseProjectTarget(
        project_id=project_id,
        label=label or (configured.label if configured else None),
        brand=brand or (configured.brand if configured else None),
        environment=environment
        or (configured.environment if configured else None)
        or inherited_environment,
        groups=groups
        if groups is not None
        else (configured.groups if configured else []),
    )
