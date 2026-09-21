"""Normalize the list of Firebase projects a multi-project change will touch."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import SelectionOption

from ..messages import msg
from ..models.targets import FirebaseProjectTarget
from ..operations.target_operations import (
    ProjectSetResolution,
    TargetResolutionError,
    filter_targets_by_environment,
    parse_environment_names,
    parse_project_ids,
    resolve_project_set,
    resolve_targets,
    target_environments,
)
from .project_prompts import ask_project_ids


def execute_firebase_select_targets_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve several Firebase projects from a caller-supplied list.

    The list comes from workflow params, a configured project set, or an
    earlier step. When a configured set spans several known environments and
    the workflow did not pass an explicit environment filter, the TUI asks
    which environments to include.

    Inputs (from ctx.data):
        project_ids (list or str, optional): Projects to target; a comma- or space-separated string is accepted.
        firebase_project_ids (list or str, optional): Same, as published by an earlier step.
        firebase_project_labels (dict, optional): project_id to label, shown instead of the raw ID.
        project_set (str, optional): Configured project set to use when project IDs are absent.
        firebase_project_set (str, optional): Same project set, as emitted by earlier steps.
        project_groups (list or str, optional): Configured project groups to keep.
        firebase_project_groups (list or str, optional): Same groups, as emitted by earlier steps.
        environment (str, optional): Configured environment(s) to keep, for example dev, pro, or both.
        firebase_environment (str, optional): Same environment, as emitted by earlier steps.
        project_filter (str, optional): Case-insensitive words used to filter the TUI project catalogue.
        firebase_project_filter (str, optional): Same filter, as emitted by earlier steps.

    Outputs (saved to ctx.data):
        firebase_targets (list[FirebaseProjectTarget]): Resolved targets.
        firebase_project_ids (list[str]): Normalized, de-duplicated project IDs.
        firebase_project_set (str, optional): Project set used, when resolved from config.
        firebase_project_groups (list[str], optional): Project groups used, when any.
        firebase_environment (str, optional): Single resolved environment, when known.
        firebase_environments (list[str]): Known environments represented by the targets.
        firebase_environment_filter (list[str], optional): Explicitly selected environment filter, when any.
        firebase_project_environments (dict[str, str]): project_id to environment.
        firebase_project_brands (dict[str, str]): project_id to brand.
        firebase_project_group_map (dict[str, list[str]]): project_id to configured groups.

    Returns:
        Success: If at least one project was named.
        Error: If the plugin is unavailable or the list is empty.
    """
    if ctx.textual:
        ctx.textual.begin_step("Proyectos Firebase")

    if not ctx.firebase:
        return _fail(ctx, "El plugin de Firebase no está disponible")

    labels = ctx.get("firebase_project_labels")
    brands = ctx.get("firebase_project_brands")
    project_environments = ctx.get("firebase_project_environments")
    project_groups_by_id = ctx.get("firebase_project_group_map")
    environment_filter = _environment_filter_from_context(ctx)
    selected_environment_filter = list(environment_filter)

    try:
        project_ids = parse_project_ids(ctx.get("project_ids")) or parse_project_ids(
            ctx.get("firebase_project_ids")
        )
        project_set_resolution: ProjectSetResolution | None = None
        if project_ids:
            targets = resolve_targets(
                project_ids,
                labels if isinstance(labels, dict) else None,
                brands if isinstance(brands, dict) else None,
                project_environments
                if isinstance(project_environments, dict)
                else None,
                project_groups_by_id
                if isinstance(project_groups_by_id, dict)
                else None,
                config=ctx.firebase.config,
            )
            if environment_filter:
                targets = filter_targets_by_environment(targets, environment_filter)
                if not targets:
                    raise TargetResolutionError(
                        "Ningun project_id coincide con los entornos "
                        f"{', '.join(environment_filter)}."
                    )
            else:
                selected_environment_filter = _ask_environment_filter(
                    ctx,
                    targets,
                    ctx.firebase.config.default_environment,
                )
                if selected_environment_filter:
                    targets = filter_targets_by_environment(
                        targets,
                        selected_environment_filter,
                    )
        else:
            project_set_resolution = resolve_project_set(
                ctx.firebase.config,
                project_set=_text(ctx.get("project_set"))
                or _text(ctx.get("firebase_project_set")),
                groups=ctx.get("project_groups") or ctx.get("firebase_project_groups"),
                environments=environment_filter,
            )
            if project_set_resolution:
                targets = project_set_resolution.targets
                if not environment_filter:
                    selected_environment_filter = _ask_environment_filter(
                        ctx,
                        targets,
                        project_set_resolution.default_environment,
                    )
                    if selected_environment_filter:
                        targets = filter_targets_by_environment(
                            targets,
                            selected_environment_filter,
                        )
            elif ctx.textual:
                targets = resolve_targets(ask_project_ids(ctx), config=ctx.firebase.config)
            else:
                targets = resolve_targets([])
        if not targets:
            raise TargetResolutionError(
                "No hay proyectos Firebase para los entornos seleccionados."
            )
    except TargetResolutionError as exc:
        return _fail(ctx, str(exc))

    if ctx.textual:
        ctx.textual.table(
            headers=list(msg.Targets.SUMMARY_HEADERS),
            rows=_brand_rows(targets),
            title=f"{len(targets)} proyectos",
            flex_column=0,
        )
        environments = target_environments(targets)
        if len(environments) > 1:
            ctx.textual.warning_text(
                "Hay varios entornos seleccionados: "
                f"{', '.join(env.upper() for env in environments)}. "
                "La publicación se confirmará proyecto a proyecto."
            )
        ctx.textual.end_step("success")

    environments = target_environments(targets)
    metadata = {
        "firebase_targets": targets,
        "firebase_project_ids": [target.project_id for target in targets],
        "firebase_environments": environments,
        "firebase_project_environments": {
            target.project_id: target.environment
            for target in targets
            if target.environment
        },
        "firebase_project_brands": {
            target.project_id: target.brand for target in targets if target.brand
        },
        "firebase_project_group_map": {
            target.project_id: target.groups for target in targets if target.groups
        },
    }
    if len(environments) == 1:
        metadata["firebase_environment"] = environments[0]
    if project_set_resolution:
        metadata["firebase_project_set"] = project_set_resolution.name
        if project_set_resolution.groups:
            metadata["firebase_project_groups"] = project_set_resolution.groups
    if selected_environment_filter:
        metadata["firebase_environment_filter"] = selected_environment_filter

    return Success(
        f"{len(targets)} proyectos Firebase",
        metadata=metadata,
    )


def _text(value: object) -> str | None:
    """Treat an empty workflow param as absent."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _environment_filter_from_context(ctx: WorkflowContext) -> list[str]:
    """Read an explicit environment filter from workflow data."""
    environment = ctx.get("environment")
    names = parse_environment_names(environment)
    if names:
        return names
    return parse_environment_names(ctx.get("firebase_environment"))


def _brand_rows(targets: list[FirebaseProjectTarget]) -> list[list[str]]:
    """Group selected targets for the compact project overview table."""
    rows_by_brand: dict[str, dict[str, list[str]]] = {}
    for target in targets:
        brand = target.brand or target.label or "—"
        row = rows_by_brand.setdefault(
            brand,
            {"environments": [], "groups": []},
        )
        if target.environment:
            environment = target.environment.upper()
            if environment not in row["environments"]:
                row["environments"].append(environment)
        for group in target.groups:
            if group not in row["groups"]:
                row["groups"].append(group)

    return [
        [
            brand,
            ", ".join(values["environments"]) if values["environments"] else "—",
            ", ".join(values["groups"]) if values["groups"] else "—",
        ]
        for brand, values in rows_by_brand.items()
    ]


def _ask_environment_filter(
    ctx: WorkflowContext,
    targets,
    default_environment: str | None,
) -> list[str]:
    """Ask which known environments to include when a set spans several."""
    environments = target_environments(targets)
    if len(environments) <= 1 or not ctx.textual:
        return []

    default_selected = {default_environment} if default_environment else set(environments)
    selected = ctx.textual.ask_multiselect(
        "Selecciona entornos Firebase:",
        [
            SelectionOption(
                value=environment,
                label=environment.upper(),
                selected=environment in default_selected,
            )
            for environment in environments
        ],
    )
    selected_environments = parse_environment_names(selected)
    if not selected_environments:
        raise TargetResolutionError("No se seleccionó ningún entorno Firebase.")
    return selected_environments


def _fail(ctx: WorkflowContext, message: str) -> WorkflowResult:
    """Report an error through the UI and the result."""
    if ctx.textual:
        ctx.textual.error_text(message)
        ctx.textual.end_step("error")
    return Error(message)
