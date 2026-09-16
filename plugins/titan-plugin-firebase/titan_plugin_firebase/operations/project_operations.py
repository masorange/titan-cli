"""Project catalogue helpers for Firebase workflows."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from ..config import FirebasePluginConfig
from ..models.view import UIFirebaseProject
from .target_operations import find_configured_project_context


def parse_project_filter(value: Any) -> list[str]:
    """
    Normalize a user-supplied project filter into case-insensitive terms.

    Commas, semicolons and whitespace are treated as separators so values such
    as "Prepago, National" and "Prepago National" both work as expected.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_parts = [str(part) for part in value]
    else:
        raw_parts = [str(value)]

    terms: list[str] = []
    for raw in raw_parts:
        normalized = raw.replace(",", " ").replace(";", " ")
        for part in normalized.split():
            term = part.strip().casefold()
            if term and term not in terms:
                terms.append(term)
    return terms


def filter_projects(
    projects: Iterable[UIFirebaseProject],
    project_filter: Any,
) -> list[UIFirebaseProject]:
    """Filter projects by project ID, display name, resource name or number."""
    terms = parse_project_filter(project_filter)
    ordered = list(projects)
    if not terms:
        return ordered

    return [
        project
        for project in ordered
        if any(term in field for term in terms for field in _search_fields(project))
    ]


def enrich_projects_with_config(
    projects: Iterable[UIFirebaseProject],
    config: FirebasePluginConfig,
) -> list[UIFirebaseProject]:
    """
    Add repository-owned metadata to Firebase Management projects.

    Firebase Management does not expose deployment environments or brand/group
    labels. Those are Titan project-set concepts, so the catalogue is enriched
    by matching each returned project ID against the plugin configuration.
    """
    return [enrich_project_with_config(project, config) for project in projects]


def enrich_project_with_config(
    project: UIFirebaseProject,
    config: FirebasePluginConfig,
) -> UIFirebaseProject:
    """Return one Firebase project annotated with configured metadata, if any."""
    context = find_configured_project_context(config, project.project_id)
    if context is None:
        return project
    configured = context.project
    return replace(
        project,
        configured_label=configured.label,
        brand=configured.brand,
        environment=configured.environment or context.default_environment,
        groups=tuple(configured.groups),
    )


def _search_fields(project: UIFirebaseProject) -> list[str]:
    """Return normalized fields used by project catalogue filtering."""
    return [
        str(value).casefold()
        for value in (
            project.project_id,
            project.display_name,
            project.configured_label,
            project.brand,
            project.environment,
            " ".join(project.groups),
            project.name,
            project.project_number,
        )
        if value
    ]
