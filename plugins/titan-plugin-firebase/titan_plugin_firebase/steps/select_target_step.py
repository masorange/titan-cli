"""Choose which Firebase project (brand/environment) the workflow acts on."""

from __future__ import annotations

from titan_cli.engine import Error, Success, WorkflowContext, WorkflowResult
from titan_cli.ui.tui.widgets import OptionItem

from ..operations.target_operations import (
    TargetResolutionError,
    available_brands,
    available_environments,
    project_id_for_brand,
    resolve_target,
)


def execute_firebase_select_target_step(ctx: WorkflowContext) -> WorkflowResult:
    """
    Resolve the Firebase project to work on.

    Inputs (from ctx.data):
        project_id (str, optional): Explicit Firebase project ID.
        brand (str, optional): Brand to resolve through the plugin config.
        environment (str, optional): Environment for multi-environment configs.

    Outputs (via result metadata):
        firebase_project_id (str): Resolved project ID.
        firebase_brand (Optional[str]): Brand behind the project, when known.
        firebase_environment (Optional[str]): Environment, when configured.
        firebase_target_label (str): User-facing reference for the target.

    Returns:
        Success: If a project could be resolved.
        Error: If the plugin is unavailable, the user cancels, or the
            configuration names no project.
    """
    if ctx.textual:
        ctx.textual.begin_step("Seleccionar proyecto Firebase")

    if not ctx.firebase:
        message = "El plugin de Firebase no está disponible"
        if ctx.textual:
            ctx.textual.error_text(message)
            ctx.textual.end_step("error")
        return Error(message)

    config = ctx.firebase.config
    project_id = ctx.get("project_id") or ctx.get("firebase_project_id")
    brand = ctx.get("brand") or ctx.get("firebase_brand")
    environment = ctx.get("environment") or ctx.get("firebase_environment")

    if not project_id and not brand:
        environment = environment or _ask_environment(ctx, config)
        brand = _ask_brand(ctx, config, environment)
        if brand is None and not config.default_project:
            message = "No se seleccionó ninguna marca"
            if ctx.textual:
                ctx.textual.error_text(message)
                ctx.textual.end_step("error")
            return Error(message)

    try:
        target = resolve_target(
            config,
            project_id=str(project_id) if project_id else None,
            brand=str(brand) if brand else None,
            environment=str(environment) if environment else None,
        )
    except TargetResolutionError as exc:
        if ctx.textual:
            ctx.textual.error_text(str(exc))
            ctx.textual.end_step("error")
        return Error(str(exc))

    if ctx.textual:
        ctx.textual.text(f"Proyecto: {target.reference()}")
        ctx.textual.end_step("success")

    return Success(
        f"Proyecto Firebase: {target.project_id}",
        metadata={
            "firebase_project_id": target.project_id,
            "firebase_brand": target.brand,
            "firebase_environment": target.environment,
            "firebase_target_label": target.reference(),
        },
    )


def _ask_environment(ctx: WorkflowContext, config) -> str | None:
    """Ask for an environment only when the config declares more than one."""
    if not ctx.textual:
        return config.default_environment

    environments = available_environments(config)
    if len(environments) <= 1:
        return config.default_environment or (
            environments[0] if environments else None
        )

    return ctx.textual.ask_option(
        "¿Qué entorno?",
        [
            OptionItem(
                value=environment,
                title=environment,
                description="Entorno declarado en brand_projects",
            )
            for environment in environments
        ],
    )


def _ask_brand(ctx: WorkflowContext, config, environment) -> str | None:
    """Ask which brand to target, showing the project each one resolves to."""
    if not ctx.textual:
        return None

    brands = available_brands(config, environment)
    if not brands:
        return None

    options = []
    for brand in brands:
        try:
            resolved = project_id_for_brand(config, brand, environment)
        except TargetResolutionError as exc:
            resolved = f"sin proyecto ({exc})"
        options.append(
            OptionItem(value=brand, title=brand, description=resolved)
        )

    if config.default_project:
        options.append(
            OptionItem(
                value=None,
                title="Proyecto por defecto",
                description=config.default_project,
            )
        )

    return ctx.textual.ask_option("¿Qué marca?", options)
