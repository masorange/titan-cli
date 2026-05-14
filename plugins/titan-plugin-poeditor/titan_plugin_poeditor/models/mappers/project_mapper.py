"""Mapper functions to convert network models to view models."""

from ..formatting import format_description, format_iso_date, get_completeness_icon
from ..network.rest import NetworkPoEditorLanguage, NetworkPoEditorProject
from ..view import UIPoEditorLanguage, UIPoEditorProject


def from_network_project(
    project: NetworkPoEditorProject,
    languages: list[NetworkPoEditorLanguage] | None = None,
    raw: dict | None = None,
) -> UIPoEditorProject:
    """Convert REST PoEditor project to UI project.

    Args:
        project: NetworkPoEditorProject from REST API
        languages: Optional list of project languages
        raw: Optional raw API response dict

    Returns:
        UIPoEditorProject ready for rendering
    """
    # Calculate overall progress based on languages
    progress_percentage: float | None = None
    if languages:
        total_percentage = sum(lang.percentage for lang in languages)
        progress_percentage = total_percentage / len(languages) if languages else 0.0

    return UIPoEditorProject(
        id=project.id,
        name=project.name,
        description=format_description(project.description),
        terms_count=project.terms,
        reference_language=project.reference_language or "N/A",
        progress_icon=get_completeness_icon(progress_percentage),
        formatted_created_at=format_iso_date(project.created),
        formatted_updated_at=format_iso_date(project.updated),
        is_public=bool(project.public),
        is_open=bool(project.open),
        fallback_language=project.fallback_language or "N/A",
        raw=raw,
    )


def from_network_language(
    language: NetworkPoEditorLanguage,
) -> UIPoEditorLanguage:
    """Convert REST PoEditor language to UI language.

    Args:
        language: NetworkPoEditorLanguage from REST API

    Returns:
        UIPoEditorLanguage ready for rendering
    """
    return UIPoEditorLanguage(
        code=language.code,
        name=language.name,
        translations=language.translations,
        percentage=language.percentage,
        progress_icon=get_completeness_icon(language.percentage),
        formatted_updated_at=format_iso_date(language.updated),
    )
