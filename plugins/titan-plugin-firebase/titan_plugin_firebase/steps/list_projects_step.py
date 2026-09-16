"""List Firebase projects available to the active ADC session."""

from __future__ import annotations

from titan_cli.core.result import ClientError, ClientSuccess
from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult

from ..operations.project_operations import (
    enrich_projects_with_config,
    filter_projects,
    parse_project_filter,
)


def execute_firebase_projects_list_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    List Firebase projects available to the active Google credentials.

    Requires:
        ctx.firebase: An initialized FirebaseClient.

    Inputs (from ctx.data):
        project_filter (str, optional): Case-insensitive words used to filter project IDs, names, resource names, or numbers.
        firebase_project_filter (str, optional): Same filter, as emitted by earlier steps.

    Outputs (saved to ctx.data):
        firebase_projects (list[UIFirebaseProject]): Projects returned by Firebase Management, enriched with configured metadata when available.
        firebase_project_ids (list[str]): Project IDs in display order.
        firebase_project_labels (dict[str, str]): project_id to configured/display label.
        firebase_project_environments (dict[str, str]): project_id to configured environment.
        firebase_project_brands (dict[str, str]): project_id to configured brand.
        firebase_project_group_map (dict[str, list[str]]): project_id to configured groups.
        firebase_project_catalog_count (int): Total projects before filtering.
        firebase_project_filter_terms (list[str]): Normalized filter terms that were applied.

    Returns:
        Success: If Firebase projects could be listed.
        Error: If Firebase is unavailable or the project list request fails.
    """
    if ctx.textual:
        ctx.textual.begin_step("Listar proyectos Firebase")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    result = ctx.firebase.list_projects()
    match result:
        case ClientSuccess(data=projects):
            projects = enrich_projects_with_config(projects, ctx.firebase.config)
        case ClientError(error_message=error_message):
            return _fail(ctx, error_message)
        case _:
            return _fail(ctx, "Respuesta inesperada al listar proyectos Firebase")

    project_filter = ctx.get("project_filter")
    filter_terms = parse_project_filter(project_filter)
    if not filter_terms:
        project_filter = ctx.get("firebase_project_filter")
        filter_terms = parse_project_filter(project_filter)

    if not filter_terms and ctx.textual and len(projects) > 25:
        project_filter = ctx.textual.ask_text(
            "Filtrar proyectos Firebase (opcional):",
            default="",
        )
        filter_terms = parse_project_filter(project_filter)
    catalog_count = len(projects)
    projects = filter_projects(projects, filter_terms)

    if ctx.textual:
        if filter_terms:
            ctx.textual.dim_text(
                f"{len(projects)} de {catalog_count} proyectos coinciden con: {', '.join(filter_terms)}"
            )
        if projects:
            ctx.textual.table(
                headers=[
                    "Proyecto",
                    "Nombre",
                    "Etiqueta",
                    "Entorno",
                    "Marca",
                    "Grupos",
                    "Numero",
                ],
                rows=[
                    [
                        project.project_id,
                        project.display_name or "—",
                        project.configured_label or "—",
                        project.environment.upper() if project.environment else "—",
                        project.brand or "—",
                        ", ".join(project.groups) if project.groups else "—",
                        project.project_number or "—",
                    ]
                    for project in projects
                ],
                title=f"{len(projects)} proyectos Firebase",
                flex_column=0,
            )
        else:
            ctx.textual.dim_text("No hay proyectos Firebase que mostrar.")
        ctx.textual.end_step("success")

    return Success(
        f"{len(projects)} proyectos Firebase disponibles",
        metadata={
            "firebase_projects": projects,
            "firebase_project_ids": [project.project_id for project in projects],
            "firebase_project_labels": {
                project.project_id: project.label
                for project in projects
                if project.label != project.project_id
            },
            "firebase_project_environments": {
                project.project_id: project.environment
                for project in projects
                if project.environment
            },
            "firebase_project_brands": {
                project.project_id: project.brand for project in projects if project.brand
            },
            "firebase_project_group_map": {
                project.project_id: list(project.groups)
                for project in projects
                if project.groups
            },
            "firebase_project_catalog_count": catalog_count,
            "firebase_project_filter_terms": filter_terms,
        },
    )


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
