"""Shared prompts for choosing Firebase projects in TUI workflows."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import WorkflowContext
from titan_cli.engine.option_item import OptionItem
from titan_cli.ui.tui.widgets import SelectionOption

from ..models.view import UIFirebaseProject
from ..operations.project_operations import (
    enrich_projects_with_config,
    filter_projects,
    parse_project_filter,
)
from ..operations.target_operations import parse_project_ids

PROJECT_FILTER_PROMPT_THRESHOLD = 25


def ask_project_id(ctx: WorkflowContext) -> Optional[str]:
    """Ask the user to choose one Firebase project, with text fallback."""
    projects = list_available_projects_for_prompt(ctx)
    if projects:
        selected = ctx.textual.ask_option(
            "Selecciona un proyecto Firebase:",
            [
                OptionItem(
                    value=project.project_id,
                    title=project.project_id,
                    description=project.description,
                )
                for project in projects
            ],
        )
        project_id = _text(selected)
        if project_id:
            return project_id

    return ask_project_id_text(ctx)


def ask_project_ids(ctx: WorkflowContext) -> list[str]:
    """Ask the user to choose several Firebase projects, with text fallback."""
    projects = list_available_projects_for_prompt(ctx)
    if projects:
        selected = ctx.textual.ask_multiselect(
            "Selecciona proyectos Firebase:",
            [
                SelectionOption(
                    value=project.project_id,
                    label=_selection_label(project),
                    selected=False,
                )
                for project in projects
            ],
        )
        project_ids = parse_project_ids(selected)
        if project_ids:
            return project_ids

    return ask_project_ids_text(ctx)


def ask_project_id_text(ctx: WorkflowContext) -> Optional[str]:
    """Ask for one project ID as text."""
    value = ctx.textual.ask_text(
        "Project ID de Firebase:",
        default="",
    )
    return _text(value)


def ask_project_ids_text(ctx: WorkflowContext) -> list[str]:
    """Ask for comma-separated project IDs as text."""
    value = ctx.textual.ask_text(
        "Project IDs de Firebase (separados por coma):",
        default="",
    )
    return parse_project_ids(value)


def list_available_projects_for_prompt(
    ctx: WorkflowContext,
) -> list[UIFirebaseProject]:
    """List available Firebase projects, returning an empty list on failure."""
    if not ctx.textual:
        return []

    loading = (
        ctx.textual.loading("Listando proyectos Firebase...")
        if ctx.textual
        else nullcontext()
    )
    with loading:
        result = ctx.firebase.list_projects()

    match result:
        case ClientSuccess(data=projects):
            enriched = enrich_projects_with_config(projects, ctx.firebase.config)
            return filter_available_projects_for_prompt(ctx, enriched)
        case ClientError(error_message=message):
            ctx.textual.warning_text(
                f"No se pudieron listar los proyectos Firebase: {message}"
            )
            return []
        case _:
            return []


def filter_available_projects_for_prompt(
    ctx: WorkflowContext,
    projects: list[UIFirebaseProject],
) -> list[UIFirebaseProject]:
    """Apply an explicit or optional TUI filter to a Firebase project catalogue."""
    project_filter = _project_filter_from_context(ctx)
    if project_filter is None and len(projects) > PROJECT_FILTER_PROMPT_THRESHOLD:
        project_filter = ctx.textual.ask_text(
            "Filtrar proyectos Firebase (opcional):",
            default="",
        )

    terms = parse_project_filter(project_filter)
    filtered = filter_projects(projects, terms)
    if terms and not filtered:
        ctx.textual.warning_text(
            "El filtro no coincide con ningun proyecto Firebase; escribe el project ID manualmente."
        )
    elif terms:
        ctx.textual.dim_text(
            f"{len(filtered)} de {len(projects)} proyectos coinciden con: {', '.join(terms)}"
        )
    return filtered


def _project_filter_from_context(ctx: WorkflowContext) -> object | None:
    """Read the project catalogue filter from workflow data."""
    project_filter = ctx.get("project_filter")
    if parse_project_filter(project_filter):
        return project_filter
    firebase_project_filter = ctx.get("firebase_project_filter")
    if parse_project_filter(firebase_project_filter):
        return firebase_project_filter
    return None


def _selection_label(project: UIFirebaseProject) -> str:
    """Render one project in a multi-select list."""
    if project.description:
        return f"{project.project_id} · {project.description}"
    return project.project_id


def _text(value: object) -> str | None:
    """Normalize empty prompt values."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None
